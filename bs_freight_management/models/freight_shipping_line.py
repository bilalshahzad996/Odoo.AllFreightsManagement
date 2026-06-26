from odoo import fields, models


class FreightShippingLine(models.Model):
    _name = 'freight.shipping.line'
    _description = 'Shipping Line / Carrier'
    _order = 'name'

    name = fields.Char(string='Shipping Line', required=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        help='Leave empty to share this carrier across all companies.')
    code = fields.Char(string='Code')
    scac_code = fields.Char(
        string='SCAC Code',
        help='Standard Carrier Alpha Code used on Bills of Lading.')
    transport_mode = fields.Selection(
        selection=[
            ('sea', 'Sea'),
            ('air', 'Air'),
            ('land', 'Land'),
        ],
        string='Mode', default='sea')
    partner_id = fields.Many2one(
        'res.partner', string='Carrier Contact',
        help='Vendor / agent record for this carrier.')
    website = fields.Char(string='Tracking Website')
    active = fields.Boolean(default=True)

    # --- Demurrage ---------------------------------------------------
    currency_id = fields.Many2one(
        'res.currency', string='Demurrage Currency',
        default=lambda self: self.env.company.currency_id)
    free_days = fields.Integer(
        string='Free Days', default=14,
        help='Number of free days at destination before demurrage charges start.')
    demurrage_rate = fields.Monetary(
        string='Demurrage Rate (per container/day)',
        currency_field='currency_id',
        help='Daily demurrage charge per container after free days expire.')

    # --- Container Tracking ------------------------------------------
    tracking_url_template = fields.Char(
        string='Tracking URL Template',
        help='URL to track containers. Use {container} as placeholder.\n'
             'e.g. https://www.maersk.com/tracking/{container}')

    shipment_count = fields.Integer(
        string='Shipments', compute='_compute_shipment_count')

    def _compute_shipment_count(self):
        data = self.env['freight.shipment']._read_group(
            domain=[('shipping_line_id', 'in', self.ids)],
            groupby=['shipping_line_id'],
            aggregates=['__count'],
        )
        mapped = {line.id: count for line, count in data}
        for record in self:
            record.shipment_count = mapped.get(record.id, 0)

    def action_view_shipments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Shipments',
            'res_model': 'freight.shipment',
            'view_mode': 'list,form',
            'domain': [('shipping_line_id', '=', self.id)],
            'context': {'default_shipping_line_id': self.id},
        }
