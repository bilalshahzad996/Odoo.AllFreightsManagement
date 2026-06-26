from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class FreightShipment(models.Model):
    _name = 'freight.shipment'
    _description = 'Freight Shipment / Job File'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_booked desc, id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        index=True, default=lambda self: ('New'))
    shipment_type = fields.Selection(
        selection=[
            ('import', 'Import'),
            ('export', 'Export'),
        ],
        string='Type', required=True, default='import', tracking=True)
    transport_mode = fields.Selection(
        selection=[
            ('sea', 'Sea'),
            ('air', 'Air'),
            ('land', 'Land'),
        ],
        string='Mode', required=True, default='sea', tracking=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('booked', 'Booked'),
            ('in_transit', 'In Transit'),
            ('arrived', 'Arrived'),
            ('cleared', 'Cleared'),
            ('delivered', 'Delivered'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status', default='draft', required=True,
        tracking=True, group_expand='_group_expand_states', index=True)

    # --- Approval ----------------------------------------------------
    approval_state = fields.Selection(
        selection=[
            ('not_required', 'Not Required'),
            ('pending', 'Pending Approval'),
            ('approved', 'Approved'),
            ('refused', 'Refused'),
        ],
        string='Approval', default='not_required',
        tracking=True, copy=False)

    # --- Parties -------------------------------------------------------
    shipper_id = fields.Many2one(
        'res.partner', string='Shipper', tracking=True)
    consignee_id = fields.Many2one(
        'res.partner', string='Consignee', tracking=True)
    customer_id = fields.Many2one(
        'res.partner', string='Customer', index=True,
        help='Account billed for this shipment.')
    shipping_line_id = fields.Many2one(
        'freight.shipping.line', string='Shipping Line', tracking=True, index=True)

    # --- Routing -------------------------------------------------------
    origin_port_id = fields.Many2one(
        'freight.port', string='Origin Port (POL)', index=True)
    destination_port_id = fields.Many2one(
        'freight.port', string='Destination Port (POD)', index=True)
    incoterm_id = fields.Many2one(
        'account.incoterms', string='Incoterms', tracking=True,
        help='International Commercial Terms governing cost and risk split.')
    date_booked = fields.Date(
        string='Booking Date', default=fields.Date.context_today)
    etd = fields.Date(string='ETD', tracking=True,
                      help='Estimated Time of Departure.')
    eta = fields.Date(string='ETA', tracking=True,
                      help='Estimated Time of Arrival.')

    # --- Documents -----------------------------------------------------
    master_bl = fields.Char(string='Master B/L', tracking=True)
    house_bl = fields.Char(string='House B/L')
    booking_ref = fields.Char(string='Carrier Booking Ref')
    customs_declaration_no = fields.Char(string='Customs Declaration No.')

    # --- Lines ---------------------------------------------------------
    container_ids = fields.One2many(
        'freight.container', 'shipment_id', string='Containers')
    charge_ids = fields.One2many(
        'freight.charge', 'shipment_id', string='Charges')
    leg_ids = fields.One2many(
        'freight.shipment.leg', 'shipment_id', string='Legs')

    container_count = fields.Integer(
        string='# Containers', compute='_compute_container_count', store=True)

    # --- Costing -------------------------------------------------------
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        related='company_id.currency_id', string='Company Currency')
    total_charges = fields.Monetary(
        string='Total Charges', currency_field='currency_id',
        compute='_compute_total_charges', store=True,
        help='Sum of all charges converted to the company currency.')

    # --- Actual dates & demurrage ------------------------------------
    date_arrived = fields.Date(string='Actual Arrival Date', tracking=True, copy=False)
    date_delivered = fields.Date(string='Actual Delivery Date', tracking=True, copy=False)
    demurrage_days = fields.Integer(
        string='Demurrage Days', compute='_compute_demurrage', store=True)
    demurrage_amount = fields.Monetary(
        string='Demurrage Amount', currency_field='currency_id',
        compute='_compute_demurrage', store=True,
        help='Estimated demurrage based on shipping line rate and free days.')

    # --- Notifications -----------------------------------------------
    eta_notification_sent = fields.Boolean(default=False, copy=False)

    # --- Invoicing -----------------------------------------------------
    invoice_count = fields.Integer(
        string='Invoices', compute='_compute_invoice_count')
    vendor_bill_count = fields.Integer(
        string='Vendor Bills', compute='_compute_vendor_bill_count')

    notes = fields.Html(string='Notes')

    # ------------------------------------------------------------------
    # Compute helpers
    # ------------------------------------------------------------------

    @api.model
    def _group_expand_states(self, states, domain):
        return [key for key, _label in self._fields['state'].selection]

    @api.depends('charge_ids.amount_company')
    def _compute_total_charges(self):
        for shipment in self:
            shipment.total_charges = sum(
                shipment.charge_ids.mapped('amount_company'))

    @api.depends('container_ids')
    def _compute_container_count(self):
        for shipment in self:
            shipment.container_count = len(shipment.container_ids)

    @api.depends(
        'date_arrived', 'date_delivered',
        'shipping_line_id.free_days', 'shipping_line_id.demurrage_rate',
        'shipping_line_id.currency_id', 'container_ids', 'company_id',
    )
    def _compute_demurrage(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.date_arrived or not rec.shipping_line_id:
                rec.demurrage_days = 0
                rec.demurrage_amount = 0.0
                continue
            free_days = rec.shipping_line_id.free_days or 0
            free_deadline = rec.date_arrived + timedelta(days=free_days)
            end_date = rec.date_delivered or today
            days = max(0, (end_date - free_deadline).days)
            rec.demurrage_days = days
            rate = rec.shipping_line_id.demurrage_rate or 0.0
            container_count = len(rec.container_ids) or 1
            raw_amount = days * rate * container_count
            # Convert from shipping line currency to company currency
            line_currency = rec.shipping_line_id.currency_id
            company_currency = rec.currency_id
            if line_currency and company_currency and line_currency != company_currency:
                rec.demurrage_amount = line_currency._convert(
                    raw_amount, company_currency,
                    rec.company_id or self.env.company,
                    rec.date_arrived,
                )
            else:
                rec.demurrage_amount = raw_amount

    def _compute_invoice_count(self):
        for rec in self:
            rec.invoice_count = self.env['account.move'].search_count([
                ('invoice_origin', '=', rec.name),
                ('move_type', '=', 'out_invoice'),
            ])

    def _compute_vendor_bill_count(self):
        for rec in self:
            rec.vendor_bill_count = self.env['account.move'].search_count([
                ('invoice_origin', '=', rec.name),
                ('move_type', '=', 'in_invoice'),
            ])

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains('eta', 'etd')
    def _check_eta_etd(self):
        for rec in self:
            if rec.eta and rec.etd and rec.eta < rec.etd:
                raise ValidationError(_(
                    'ETA (%s) cannot be earlier than ETD (%s) on shipment %s.'
                ) % (rec.eta, rec.etd, rec.name))

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == 'New':
                seq_code = 'freight.shipment.%s' % vals.get(
                    'shipment_type', 'import')
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code(seq_code)
                    or self.env['ir.sequence'].next_by_code(
                        'freight.shipment')
                    or 'New')
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Approval helpers
    # ------------------------------------------------------------------

    def _get_approval_threshold(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'freight_forwarding.approval_threshold', '10000')
        try:
            return float(param)
        except (TypeError, ValueError):
            return 10000.0

    def _approval_required(self, rec):
        enabled = self.env['ir.config_parameter'].sudo().get_param(
            'freight_forwarding.approval_required', 'False')
        if enabled not in ('1', 'True', 'true'):
            return False
        return rec.total_charges >= self._get_approval_threshold()

    def action_submit_approval(self):
        self.write({'approval_state': 'pending'})
        for rec in self:
            rec.message_post(body=_(
                'Shipment submitted for manager approval. '
                'Total charges: %(amount)s %(currency)s'
            ) % {'amount': rec.total_charges, 'currency': rec.currency_id.name})

    def action_approve(self):
        self.write({'approval_state': 'approved'})
        for rec in self:
            rec.message_post(body=_('Approved by %s.') % self.env.user.name)

    def action_refuse(self):
        self.write({'approval_state': 'refused'})
        for rec in self:
            rec.message_post(body=_('Approval refused by %s.') % self.env.user.name)

    # ------------------------------------------------------------------
    # State notification helper
    # ------------------------------------------------------------------

    def _send_state_notification(self):
        template = self.env.ref(
            'freight_forwarding.mail_template_freight_state_notification',
            raise_if_not_found=False)
        if not template:
            return
        for rec in self:
            emails = []
            if rec.customer_id and rec.customer_id.email:
                emails.append(rec.customer_id.email)
            if (rec.consignee_id and rec.consignee_id.email
                    and rec.consignee_id.email not in emails):
                emails.append(rec.consignee_id.email)
            if not emails:
                continue
            template.send_mail(rec.id, force_send=True, email_values={
                'email_to': ','.join(emails),
                'email_from': rec.company_id.email or self.env.user.email or '',
            })

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def action_book(self):
        for rec in self:
            missing = []
            if not rec.shipper_id:
                missing.append(_('Shipper'))
            if not rec.consignee_id:
                missing.append(_('Consignee'))
            if not rec.customer_id:
                missing.append(_('Customer'))
            if not rec.origin_port_id:
                missing.append(_('Origin Port'))
            if not rec.destination_port_id:
                missing.append(_('Destination Port'))
            if not rec.shipping_line_id:
                missing.append(_('Shipping Line'))
            if missing:
                raise UserError(_(
                    'Please fill in the following required fields before booking:\n%s'
                ) % '\n'.join('• ' + f for f in missing))
            if self._approval_required(rec) and rec.approval_state != 'approved':
                raise UserError(_(
                    'Total charges (%(amount)s %(currency)s) exceed the approval '
                    'threshold (%(threshold)s %(currency)s). '
                    'Please submit for manager approval first.'
                ) % {
                    'amount': '%.2f' % rec.total_charges,
                    'currency': rec.currency_id.name,
                    'threshold': '%.2f' % self._get_approval_threshold(),
                })
        self.write({'state': 'booked'})
        self._send_state_notification()

    def action_in_transit(self):
        for rec in self:
            if not rec.etd:
                raise UserError(_(
                    'Please set the ETD before marking the shipment as In Transit.'))
            if not rec.booking_ref and not rec.master_bl:
                raise UserError(_(
                    'A Carrier Booking Reference or Master B/L number is required '
                    'before marking the shipment as In Transit.'))
        self.write({'state': 'in_transit'})
        self._send_state_notification()

    def action_arrived(self):
        for rec in self:
            if not rec.eta:
                raise UserError(_(
                    'Please set the ETA before marking the shipment as Arrived.'))
        today = fields.Date.context_today(self)
        self.write({'state': 'arrived', 'date_arrived': today})
        self._send_state_notification()

    def action_cleared(self):
        self.write({'state': 'cleared'})
        self._send_state_notification()

    def action_delivered(self):
        today = fields.Date.context_today(self)
        self.write({'state': 'delivered', 'date_delivered': today})
        self._send_state_notification()

    def action_cancel(self):
        self.write({'state': 'cancelled'})
        self._send_state_notification()

    def action_reset_to_draft(self):
        self.write({'state': 'draft', 'approval_state': 'not_required'})

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def action_view_containers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Containers',
            'res_model': 'freight.container',
            'view_mode': 'list,form',
            'domain': [('shipment_id', '=', self.id)],
            'context': {'default_shipment_id': self.id},
        }

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Customer Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [
                ('invoice_origin', '=', self.name),
                ('move_type', '=', 'out_invoice'),
            ],
        }

    def action_view_vendor_bills(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vendor Bills'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [
                ('invoice_origin', '=', self.name),
                ('move_type', '=', 'in_invoice'),
            ],
        }

    # ------------------------------------------------------------------
    # Invoicing
    # ------------------------------------------------------------------

    def _default_income_account(self):
        company = self.company_id or self.env.company
        return self.env['account.account'].search([
            ('account_type', 'in', ['income', 'income_other']),
            ('company_ids', 'in', company.ids),
        ], limit=1)

    def _default_expense_account(self):
        company = self.company_id or self.env.company
        return self.env['account.account'].search([
            ('account_type', '=', 'expense'),
            ('company_ids', 'in', company.ids),
        ], limit=1)

    def action_create_invoice(self):
        self.ensure_one()
        if not self.customer_id:
            raise UserError(_('Please set a Customer before creating an invoice.'))
        if not self.charge_ids:
            raise UserError(_('No charges found on this shipment.'))

        default_account = self._default_income_account()
        lines = []
        for charge in self.charge_ids:
            account = charge.charge_type_id.income_account_id or default_account
            if not account:
                raise UserError(_(
                    'No income account found. Please configure one on Charge Type '
                    '"%s" or ensure a default income account exists in your chart of accounts.'
                ) % charge.charge_type_id.name)
            lines.append((0, 0, {
                'name': charge.name or charge.charge_type_id.name,
                'quantity': 1.0,
                'price_unit': charge.amount,
                'currency_id': charge.currency_id.id,
                'account_id': account.id,
            }))

        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.customer_id.id,
            'invoice_origin': self.name,
            'currency_id': self.currency_id.id,
            'invoice_line_ids': lines,
            'narration': _('Freight charges for shipment %s') % self.name,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
        }

    # ------------------------------------------------------------------
    # Tariff application
    # ------------------------------------------------------------------

    def action_apply_tariff(self):
        self.ensure_one()
        tariffs = self.env['freight.tariff'].search_matching(self)
        if not tariffs:
            raise UserError(_(
                'No active tariff rates found matching this shipment\'s route, '
                'carrier, and transport mode.'))
        # Deduplicate: skip tariff charges already on this shipment
        existing = set(self.charge_ids.filtered('name').mapped('name'))
        created = skipped = 0
        today = fields.Date.context_today(self)
        for tariff in tariffs:
            if tariff.name in existing:
                skipped += 1
                continue
            self.env['freight.charge'].create({
                'shipment_id': self.id,
                'charge_type_id': tariff.charge_type_id.id,
                'name': tariff.name,
                'currency_id': tariff.currency_id.id,
                'amount': tariff.rate,
                'date': today,
            })
            existing.add(tariff.name)
            created += 1
        if created == 0:
            raise UserError(_(
                'All matching tariff charges already exist on this shipment.'))
        msg = _('%d charge(s) added from tariff rates.') % created
        if skipped:
            msg += ' ' + _('%d already existed and were skipped.') % skipped
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Tariff Applied'),
                'message': msg,
                'type': 'success',
                'sticky': False,
            },
        }

    def action_create_demurrage_charge(self):
        self.ensure_one()
        if not self.demurrage_days:
            raise UserError(_('No demurrage days calculated. Please set Actual Arrival Date first.'))
        demurrage_type = self.env['freight.charge.type'].search(
            [('code', '=', 'DEM')], limit=1)
        if not demurrage_type:
            raise UserError(_(
                'Demurrage charge type (code: DEM) not found. '
                'Please create it under Configuration → Charge Types.'))
        existing = self.charge_ids.filtered(
            lambda c: c.charge_type_id == demurrage_type)
        if existing:
            raise UserError(_(
                'A demurrage charge already exists on this shipment. '
                'Remove it first if you want to recalculate.'))
        self.env['freight.charge'].create({
            'shipment_id': self.id,
            'charge_type_id': demurrage_type.id,
            'name': _('Demurrage — %d days') % self.demurrage_days,
            'amount': self.demurrage_amount,
            'currency_id': self.currency_id.id,
            'date': fields.Date.context_today(self),
            'partner_id': self.shipping_line_id.partner_id.id or False,
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Demurrage Charge Created'),
                'message': _('%d day(s) × rate = %s added as a charge.')
                    % (self.demurrage_days, self.demurrage_amount),
                'type': 'success',
                'sticky': False,
            },
        }

    # ------------------------------------------------------------------
    # Cron — ETA approaching notifications
    # ------------------------------------------------------------------

    @api.model
    def _cron_eta_notifications(self):
        target_date = fields.Date.context_today(self) + timedelta(days=3)
        shipments = self.search([
            ('state', '=', 'in_transit'),
            ('eta', '=', target_date),
            ('eta_notification_sent', '=', False),
            ('customer_id', '!=', False),
        ])
        template = self.env.ref(
            'freight_forwarding.mail_template_freight_eta_approaching',
            raise_if_not_found=False)
        for shipment in shipments:
            if template and shipment.customer_id.email:
                template.send_mail(shipment.id, force_send=True)
            shipment.message_post(body=_(
                'ETA approaching notification sent to %s.'
            ) % (shipment.customer_id.name or 'customer'))
            shipment.eta_notification_sent = True

    def action_create_vendor_bills(self):
        self.ensure_one()
        vendor_charges = self.charge_ids.filtered('partner_id')
        if not vendor_charges:
            raise UserError(_(
                'No charges have a Vendor assigned. '
                'Please set a Vendor on the charges before creating vendor bills.'))

        by_vendor = {}
        for charge in vendor_charges:
            by_vendor.setdefault(charge.partner_id.id, []).append(charge)

        default_account = self._default_expense_account()
        bill_ids = []
        for partner_id, charges in by_vendor.items():
            lines = []
            for charge in charges:
                account = charge.charge_type_id.expense_account_id or default_account
                if not account:
                    raise UserError(_(
                        'No expense account found. Please configure one on Charge Type '
                        '"%s" or ensure a default expense account exists.'
                    ) % charge.charge_type_id.name)
                lines.append((0, 0, {
                    'name': charge.name or charge.charge_type_id.name,
                    'quantity': 1.0,
                    'price_unit': charge.amount,
                    'currency_id': charge.currency_id.id,
                    'account_id': account.id,
                }))
            bill = self.env['account.move'].create({
                'move_type': 'in_invoice',
                'partner_id': partner_id,
                'invoice_origin': self.name,
                'invoice_line_ids': lines,
                'narration': _('Freight charges for shipment %s') % self.name,
            })
            bill_ids.append(bill.id)

        if len(bill_ids) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'res_id': bill_ids[0],
                'view_mode': 'form',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vendor Bills'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', bill_ids)],
        }
