from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FreightCharge(models.Model):
    _name = 'freight.charge'
    _description = 'Freight Charge / Expense'
    _order = 'shipment_id, date, id'

    shipment_id = fields.Many2one(
        'freight.shipment', string='Shipment',
        required=True, ondelete='cascade', index=True)
    charge_type_id = fields.Many2one(
        'freight.charge.type', string='Charge Type', required=True)
    name = fields.Char(string='Description')
    date = fields.Date(
        string='Date', default=fields.Date.context_today)
    partner_id = fields.Many2one(
        'res.partner', string='Vendor',
        help='Supplier billing this charge (carrier, agent, customs broker).')

    # --- Multi-currency amounts ---------------------------------------
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        default=lambda self: self.env.company.currency_id)
    amount = fields.Monetary(
        string='Amount', currency_field='currency_id')

    company_id = fields.Many2one(
        related='shipment_id.company_id', store=True)
    company_currency_id = fields.Many2one(
        related='company_id.currency_id', string='Company Currency')
    amount_company = fields.Monetary(
        string='Amount (Company Currency)',
        currency_field='company_currency_id',
        compute='_compute_amount_company', store=True,
        help='Charge amount converted to the company currency at the '
             'charge date rate.')

    @api.depends('amount', 'currency_id', 'company_currency_id', 'date')
    def _compute_amount_company(self):
        for charge in self:
            from_currency = charge.currency_id
            to_currency = charge.company_currency_id
            if not from_currency or not to_currency:
                charge.amount_company = charge.amount
                continue
            charge.amount_company = from_currency._convert(
                from_amount=charge.amount,
                to_currency=to_currency,
                company=charge.company_id or self.env.company,
                date=charge.date or fields.Date.context_today(self),
            )

    @api.constrains('shipment_id')
    def _check_shipment_not_cancelled(self):
        for charge in self:
            if charge.shipment_id.state == 'cancelled':
                raise ValidationError(_(
                    'Cannot add charges to cancelled shipment "%s".'
                ) % charge.shipment_id.name)

    @api.onchange('charge_type_id')
    def _onchange_charge_type_id(self):
        if self.charge_type_id and not self.name:
            self.name = self.charge_type_id.name
