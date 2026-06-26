{
    'name': 'Supply Chain & Freight Management',
    'version': '19.0.3.0.0',
    'category': 'Inventory/Freight',
    'summary': 'Manage import/export shipments: containers, shipping lines, '
               'port clearance fees and multi-currency expenses.',
    'description': """
Supply Chain & Freight Forwarding
=================================

An operational module tailored for freight forwarders and import/export
businesses:

* Shipment job files (import / export, sea / air / land)
* Container tracking (number, type, seal, weight, HS codes, customs values, tracking URL)
* Shipping line / carrier master data with demurrage settings
* Port master data (UN/LOCODE) — 50+ seeded ports
* Multi-leg routing (transshipment support)
* Multi-currency expense / charge tracking (port clearance, THC, customs, ...)
* Automatic conversion of charges to the company currency
* Incoterms on every shipment
* State transition validation (mandatory fields, date checks)
* Manager approval workflow for high-value shipments (configurable threshold)
* Demurrage auto-calculation based on free days and daily rate
* Customer invoice and vendor bill generation from charges
* Tariff / rate card management with "Apply Tariff" action
* Shipment PDF report (Bill of Lading / Job File)
* ETA approaching email notification (3-day warning via scheduled cron)
* KPI graph and pivot views
""",
    'author': 'DevFlow',
    'price': '125',
    'currency': 'USD',
    'maintainer': 'DevFlow'.
    'license': 'LGPL-3',
    'depends': ['mail', 'contacts', 'account', 'base_setup'],
    'data': [
        'security/freight_security.xml',
        'security/ir.model.access.csv',
        'data/freight_sequence.xml',
        'data/freight_charge_type_data.xml',
        'data/freight_port_data.xml',
        'data/freight_port_data_extra.xml',
        'data/freight_cron.xml',
        'data/freight_mail_template.xml',
        'data/freight_state_notification_template.xml',
        'views/freight_shipping_line_views.xml',
        'views/freight_port_views.xml',
        'views/freight_charge_type_views.xml',
        'views/freight_charge_views.xml',
        'views/freight_container_views.xml',
        'views/freight_shipment_views.xml',
        'views/freight_tariff_views.xml',
        'views/freight_shipment_leg_views.xml',
        'views/freight_menus.xml',
        'views/res_config_settings_views.xml',
        'report/freight_shipment_report.xml',
    ],
    'demo': [
        'demo/freight_demo.xml',
    ],
    'application': True,
    'installable': True,
}
