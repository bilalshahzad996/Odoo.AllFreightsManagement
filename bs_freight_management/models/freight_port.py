from odoo import api, fields, models


class FreightPort(models.Model):
    _name = 'freight.port'
    _description = 'Port'
    _order = 'name'

    name = fields.Char(string='Port Name', required=True)
    code = fields.Char(
        string='UN/LOCODE',
        help='United Nations Code for Trade and Transport Locations '
             '(e.g. CNSHA for Shanghai).')
    country_id = fields.Many2one('res.country', string='Country')
    port_type = fields.Selection(
        selection=[
            ('sea', 'Seaport'),
            ('air', 'Airport'),
            ('land', 'Inland / Dry Port'),
        ],
        string='Type', default='sea')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        help='Leave empty to share this port across all companies.')

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for record in self:
            if record.code:
                record.display_name = '%s (%s)' % (record.name, record.code)
            else:
                record.display_name = record.name or ''
