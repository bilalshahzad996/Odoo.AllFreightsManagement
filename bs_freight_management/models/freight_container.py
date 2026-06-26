from odoo import api, fields, models


class FreightContainer(models.Model):
    _name = 'freight.container'
    _description = 'Shipping Container'
    _order = 'name'

    name = fields.Char(string='Container No.', required=True)
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
        string='Type', default='40hc')
    seal_number = fields.Char(string='Seal No.')
    shipment_id = fields.Many2one(
        'freight.shipment', string='Shipment',
        ondelete='cascade', index=True)
    package_count = fields.Integer(string='Packages')
    gross_weight = fields.Float(string='Gross Weight (kg)')
    volume = fields.Float(string='Volume (CBM)')
    company_id = fields.Many2one(
        related='shipment_id.company_id', store=True)

    # --- Customs / HS Code -------------------------------------------
    hs_code = fields.Char(
        string='HS Code',
        help='Harmonized System tariff classification code (e.g. 8471.30).')
    commodity_description = fields.Char(string='Commodity Description')
    country_of_origin_id = fields.Many2one(
        'res.country', string='Country of Origin', ondelete='restrict', index=True)
    customs_currency_id = fields.Many2one(
        'res.currency', string='Customs Currency',
        default=lambda self: self.env.company.currency_id)
    customs_value = fields.Monetary(
        string='Declared Customs Value',
        currency_field='customs_currency_id',
        help='Value declared to customs authorities for duty calculation.')

    # --- Container Tracking ------------------------------------------
    tracking_status = fields.Selection(
        selection=[
            ('unknown', 'Unknown'),
            ('in_transit', 'In Transit'),
            ('arrived', 'Arrived'),
            ('delivered', 'Delivered'),
        ],
        string='Tracking Status', default='unknown')
    last_tracking_event = fields.Char(string='Last Tracking Event')
    last_tracking_date = fields.Datetime(string='Last Updated')
    tracking_url = fields.Char(
        string='Tracking URL', compute='_compute_tracking_url', store=False)

    def _compute_tracking_url(self):
        for rec in self:
            template = rec.shipment_id.shipping_line_id.tracking_url_template
            if template and rec.name:
                try:
                    rec.tracking_url = template.replace('{container}', rec.name)
                except Exception:
                    rec.tracking_url = False
            else:
                rec.tracking_url = False

    _name_shipment_uniq = models.Constraint(
        'unique(name, shipment_id)',
        'A container number must be unique within a shipment.',
    )

    @api.depends('name', 'container_type')
    def _compute_display_name(self):
        type_labels = dict(self._fields['container_type'].selection)
        for record in self:
            label = type_labels.get(record.container_type)
            if label:
                record.display_name = '%s [%s]' % (record.name, label)
            else:
                record.display_name = record.name or ''
