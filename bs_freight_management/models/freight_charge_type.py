from odoo import fields, models


class FreightChargeType(models.Model):
    _name = 'freight.charge.type'
    _description = 'Freight Charge Type'
    _order = 'sequence, name'

    name = fields.Char(string='Charge Type', required=True, translate=True)
    code = fields.Char(string='Code')
    category = fields.Selection(
        selection=[
            ('freight', 'Freight'),
            ('port', 'Port / Terminal'),
            ('clearance', 'Customs Clearance'),
            ('documentation', 'Documentation'),
            ('handling', 'Handling'),
            ('insurance', 'Insurance'),
            ('other', 'Other'),
        ],
        string='Category', default='other', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # --- GL Accounts for invoicing ------------------------------------
    income_account_id = fields.Many2one(
        'account.account',
        string='Income Account',
        domain=[('account_type', 'in', ['income', 'income_other'])],
        help='Account credited when invoicing this charge to a customer.')
    expense_account_id = fields.Many2one(
        'account.account',
        string='Expense Account',
        domain=[('account_type', '=', 'expense')],
        help='Account debited when billing this charge from a vendor.')
