from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    freight_approval_required = fields.Boolean(
        string='Require Manager Approval for High-Value Shipments',
        config_parameter='freight_forwarding.approval_required',
        help='When enabled, shipments whose total charges exceed the threshold '
             'must be approved by a Freight Manager before booking.')
    freight_approval_threshold = fields.Float(
        string='Approval Threshold (Company Currency)',
        config_parameter='freight_forwarding.approval_threshold',
        default=10000.0,
        help='Shipments with total charges at or above this amount require '
             'manager approval before they can be booked.')
