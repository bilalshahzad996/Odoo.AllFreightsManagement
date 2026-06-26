from odoo import _, api, fields, models


class FreightTariff(models.Model):
    _name = 'freight.tariff'
    _description = 'Freight Tariff / Rate Card'
    _order = 'shipping_line_id, origin_port_id, destination_port_id, sequence'

    name = fields.Char(string='Rate Name', required=True)
    sequence = fields.Integer(default=10)
    shipping_line_id = fields.Many2one(
        'freight.shipping.line', string='Shipping Line / Carrier')
    origin_port_id = fields.Many2one('freight.port', string='Origin Port')
    destination_port_id = fields.Many2one('freight.port', string='Destination Port')
    transport_mode = fields.Selection(
        selection=[('sea', 'Sea'), ('air', 'Air'), ('land', 'Land')],
        string='Mode')
    charge_type_id = fields.Many2one(
        'freight.charge.type', string='Charge Type', required=True)
    container_type = fields.Selection(
        selection=[
            ('20gp', "20' General Purpose"),
            ('40gp', "40' General Purpose"),
            ('40hc', "40' High Cube"),
            ('45hc', "45' High Cube"),
            ('20rf', "20' Reefer"),
            ('40rf', "40' Reefer"),
            ('20ot', "20' Open Top"),
            ('40ot', "40' Open Top"),
            ('20fr', "20' Flat Rack"),
            ('40fr', "40' Flat Rack"),
            ('lcl', 'LCL / Loose'),
        ],
        string='Container Type',
        help='Leave empty to apply to all container types.')
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id, required=True)
    rate = fields.Monetary(
        string='Rate', currency_field='currency_id', required=True)
    valid_from = fields.Date(string='Valid From')
    valid_to = fields.Date(string='Valid To')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company)
    notes = fields.Text(string='Notes')

    def _is_valid_today(self):
        today = fields.Date.context_today(self)
        if self.valid_from and self.valid_from > today:
            return False
        if self.valid_to and self.valid_to < today:
            return False
        return True

    @api.model
    def search_matching(self, shipment):
        today = fields.Date.context_today(self)
        domain = [
            '|', ('origin_port_id', '=', False),
                 ('origin_port_id', '=', shipment.origin_port_id.id),
            '|', ('destination_port_id', '=', False),
                 ('destination_port_id', '=', shipment.destination_port_id.id),
            '|', ('shipping_line_id', '=', False),
                 ('shipping_line_id', '=', shipment.shipping_line_id.id),
            '|', ('transport_mode', '=', False),
                 ('transport_mode', '=', shipment.transport_mode),
            '|', ('valid_from', '=', False),
                 ('valid_from', '<=', today),
            '|', ('valid_to', '=', False),
                 ('valid_to', '>=', today),
        ]
        return self.search(domain)
