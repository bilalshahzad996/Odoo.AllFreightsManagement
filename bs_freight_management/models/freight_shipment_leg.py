from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FreightShipmentLeg(models.Model):
    _name = 'freight.shipment.leg'
    _description = 'Shipment Leg (Transshipment)'
    _order = 'shipment_id, sequence, id'

    shipment_id = fields.Many2one(
        'freight.shipment', string='Shipment',
        required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    leg_type = fields.Selection(
        selection=[('sea', 'Sea'), ('air', 'Air'), ('land', 'Land')],
        string='Mode', default='sea', required=True)
    origin_port_id = fields.Many2one(
        'freight.port', string='From Port', ondelete='restrict', index=True)
    destination_port_id = fields.Many2one(
        'freight.port', string='To Port', ondelete='restrict', index=True)
    shipping_line_id = fields.Many2one(
        'freight.shipping.line', string='Carrier', ondelete='restrict', index=True)
    vessel_name = fields.Char(string='Vessel / Flight')
    voyage_no = fields.Char(string='Voyage / Flight No.')
    etd = fields.Date(string='ETD')
    eta = fields.Date(string='ETA')
    bl_number = fields.Char(string='B/L No.')
    status = fields.Selection(
        selection=[
            ('planned', 'Planned'),
            ('in_transit', 'In Transit'),
            ('arrived', 'Arrived'),
        ],
        string='Status', default='planned', required=True)
    company_id = fields.Many2one(
        related='shipment_id.company_id', store=True)

    @api.constrains('eta', 'etd')
    def _check_leg_eta_etd(self):
        for leg in self:
            if leg.eta and leg.etd and leg.eta < leg.etd:
                raise ValidationError(_(
                    'Leg ETA (%s) cannot be earlier than ETD (%s).'
                ) % (leg.eta, leg.etd))
