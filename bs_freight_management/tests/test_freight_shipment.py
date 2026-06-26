from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestFreightShipment(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Ports
        cls.port_a = cls.env['freight.port'].create({'name': 'Test Port A', 'code': 'TSTA'})
        cls.port_b = cls.env['freight.port'].create({'name': 'Test Port B', 'code': 'TSTB'})

        # Partners
        cls.customer = cls.env['res.partner'].create({'name': 'Test Customer', 'email': 'customer@test.com'})
        cls.shipper = cls.env['res.partner'].create({'name': 'Test Shipper'})
        cls.consignee = cls.env['res.partner'].create({'name': 'Test Consignee'})
        cls.vendor = cls.env['res.partner'].create({'name': 'Test Vendor'})

        # Shipping line with demurrage
        cls.shipping_line = cls.env['freight.shipping.line'].create({
            'name': 'Test Line',
            'free_days': 14,
            'demurrage_rate': 50.0,
            'currency_id': cls.env.company.currency_id.id,
        })

        # Charge type
        cls.charge_type = cls.env['freight.charge.type'].create({'name': 'Ocean Freight', 'code': 'OF'})

        cls._base_vals = {
            'shipment_type': 'import',
            'transport_mode': 'sea',
            'customer_id': cls.customer.id,
            'shipper_id': cls.shipper.id,
            'consignee_id': cls.consignee.id,
            'origin_port_id': cls.port_a.id,
            'destination_port_id': cls.port_b.id,
            'shipping_line_id': cls.shipping_line.id,
        }

    def _make_shipment(self, **kwargs):
        vals = dict(self._base_vals)
        vals.update(kwargs)
        return self.env['freight.shipment'].create(vals)

    # ------------------------------------------------------------------
    # Sequence
    # ------------------------------------------------------------------

    def test_shipment_sequence(self):
        s = self._make_shipment()
        self.assertTrue(s.name and s.name != 'New', "Sequence should be assigned on create")

    # ------------------------------------------------------------------
    # Booking validation
    # ------------------------------------------------------------------

    def test_action_book_missing_customer(self):
        s = self.env['freight.shipment'].create({
            'shipment_type': 'import',
            'transport_mode': 'sea',
            'shipper_id': self.shipper.id,
            'consignee_id': self.consignee.id,
            'origin_port_id': self.port_a.id,
            'destination_port_id': self.port_b.id,
        })
        with self.assertRaises(UserError):
            s.action_book()

    def test_action_book_missing_ports(self):
        s = self.env['freight.shipment'].create({
            'shipment_type': 'import',
            'transport_mode': 'sea',
            'customer_id': self.customer.id,
            'shipper_id': self.shipper.id,
            'consignee_id': self.consignee.id,
        })
        with self.assertRaises(UserError):
            s.action_book()

    def test_action_book_success(self):
        s = self._make_shipment()
        s.action_book()
        self.assertEqual(s.state, 'booked')

    # ------------------------------------------------------------------
    # ETA / ETD constraint
    # ------------------------------------------------------------------

    def test_eta_before_etd_raises(self):
        with self.assertRaises(ValidationError):
            self._make_shipment(etd='2025-06-20', eta='2025-06-10')

    def test_eta_after_etd_ok(self):
        s = self._make_shipment(etd='2025-06-10', eta='2025-06-20')
        self.assertTrue(s.id)

    # ------------------------------------------------------------------
    # Approval workflow
    # ------------------------------------------------------------------

    def test_approval_flow(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'freight_forwarding.approval_required', True)
        self.env['ir.config_parameter'].sudo().set_param(
            'freight_forwarding.approval_threshold', '100.0')
        s = self._make_shipment()
        self.env['freight.charge'].create({
            'shipment_id': s.id,
            'charge_type_id': self.charge_type.id,
            'name': 'Freight',
            'amount': 500.0,
            'currency_id': self.env.company.currency_id.id,
        })
        # Submit → pending
        s.action_submit_approval()
        self.assertEqual(s.approval_state, 'pending')
        # Approve → approved, then book goes through
        s.action_approve()
        self.assertEqual(s.approval_state, 'approved')
        s.action_book()
        self.assertEqual(s.state, 'booked')

    def test_approval_refuse(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'freight_forwarding.approval_required', True)
        self.env['ir.config_parameter'].sudo().set_param(
            'freight_forwarding.approval_threshold', '100.0')
        s = self._make_shipment()
        self.env['freight.charge'].create({
            'shipment_id': s.id,
            'charge_type_id': self.charge_type.id,
            'name': 'Freight',
            'amount': 500.0,
            'currency_id': self.env.company.currency_id.id,
        })
        s.action_submit_approval()
        s.action_refuse()
        self.assertEqual(s.approval_state, 'refused')

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def test_action_in_transit_no_etd(self):
        s = self._make_shipment()
        s.action_book()
        with self.assertRaises(UserError):
            s.action_in_transit()

    def test_action_in_transit_no_bl(self):
        s = self._make_shipment(etd='2025-06-10')
        s.action_book()
        with self.assertRaises(UserError):
            s.action_in_transit()

    def test_action_arrived_no_eta(self):
        s = self._make_shipment(etd='2025-06-10', booking_ref='BK001')
        s.action_book()
        s.action_in_transit()
        with self.assertRaises(UserError):
            s.action_arrived()

    def test_full_state_flow(self):
        s = self._make_shipment(
            etd='2025-06-10', eta='2025-07-01', booking_ref='BK002')
        s.action_book()
        self.assertEqual(s.state, 'booked')
        s.action_in_transit()
        self.assertEqual(s.state, 'in_transit')
        s.action_arrived()
        self.assertEqual(s.state, 'arrived')
        self.assertTrue(s.date_arrived)
        s.action_cleared()
        self.assertEqual(s.state, 'cleared')
        s.action_delivered()
        self.assertEqual(s.state, 'delivered')
        self.assertTrue(s.date_delivered)

    def test_cancel_and_reset(self):
        s = self._make_shipment()
        s.action_book()
        s.action_cancel()
        self.assertEqual(s.state, 'cancelled')
        s.action_reset_to_draft()
        self.assertEqual(s.state, 'draft')

    # ------------------------------------------------------------------
    # Invoicing
    # ------------------------------------------------------------------

    def test_create_invoice(self):
        s = self._make_shipment()
        self.env['freight.charge'].create({
            'shipment_id': s.id,
            'charge_type_id': self.charge_type.id,
            'name': 'Freight',
            'amount': 1000.0,
            'currency_id': self.env.company.currency_id.id,
        })
        s.action_create_invoice()
        self.assertEqual(s.invoice_count, 1)
        inv = self.env['account.move'].search([
            ('invoice_origin', '=', s.name),
            ('move_type', '=', 'out_invoice'),
        ])
        self.assertTrue(inv)

    def test_create_vendor_bills(self):
        s = self._make_shipment()
        for i in range(2):
            self.env['freight.charge'].create({
                'shipment_id': s.id,
                'charge_type_id': self.charge_type.id,
                'name': 'Charge %d' % i,
                'amount': 200.0,
                'currency_id': self.env.company.currency_id.id,
                'partner_id': self.vendor.id,
            })
        s.action_create_vendor_bills()
        self.assertEqual(s.vendor_bill_count, 1)

    # ------------------------------------------------------------------
    # Demurrage
    # ------------------------------------------------------------------

    def test_demurrage_calculation(self):
        from odoo import fields as odoo_fields
        s = self._make_shipment(
            etd='2025-06-01', eta='2025-06-15', booking_ref='BK003')
        self.env['freight.container'].create({
            'name': 'TCKU1234567',
            'shipment_id': s.id,
            'container_type': '40hc',
        })
        s.action_book()
        s.action_in_transit()
        s.action_arrived()
        # Simulate arrived 20 days ago — write date_arrived directly
        from datetime import date, timedelta
        arrived_date = date.today() - timedelta(days=20)
        s.write({'date_arrived': arrived_date})
        s._compute_demurrage()
        # free_days=14, 20 days elapsed → 6 days demurrage
        self.assertEqual(s.demurrage_days, 6)
        self.assertAlmostEqual(s.demurrage_amount, 6 * 50.0 * 1, places=2)

    # ------------------------------------------------------------------
    # Tariff
    # ------------------------------------------------------------------

    def test_tariff_apply(self):
        tariff = self.env['freight.tariff'].create({
            'name': 'Test Rate',
            'charge_type_id': self.charge_type.id,
            'origin_port_id': self.port_a.id,
            'destination_port_id': self.port_b.id,
            'shipping_line_id': self.shipping_line.id,
            'transport_mode': 'sea',
            'currency_id': self.env.company.currency_id.id,
            'rate': 750.0,
        })
        s = self._make_shipment()
        s.action_apply_tariff()
        self.assertEqual(len(s.charge_ids), 1)
        self.assertAlmostEqual(s.charge_ids[0].amount, 750.0)

    # ------------------------------------------------------------------
    # Multi-currency total
    # ------------------------------------------------------------------

    def test_total_charges_computed(self):
        s = self._make_shipment()
        self.env['freight.charge'].create({
            'shipment_id': s.id,
            'charge_type_id': self.charge_type.id,
            'name': 'Freight',
            'amount': 1500.0,
            'currency_id': self.env.company.currency_id.id,
        })
        self.assertAlmostEqual(s.total_charges, 1500.0)

    # ------------------------------------------------------------------
    # Legs
    # ------------------------------------------------------------------

    def test_leg_eta_before_etd_raises(self):
        s = self._make_shipment()
        with self.assertRaises(ValidationError):
            self.env['freight.shipment.leg'].create({
                'shipment_id': s.id,
                'leg_type': 'sea',
                'etd': '2025-06-20',
                'eta': '2025-06-10',
            })

    def test_leg_create_ok(self):
        s = self._make_shipment()
        leg = self.env['freight.shipment.leg'].create({
            'shipment_id': s.id,
            'leg_type': 'sea',
            'origin_port_id': self.port_a.id,
            'destination_port_id': self.port_b.id,
            'etd': '2025-06-10',
            'eta': '2025-06-25',
        })
        self.assertEqual(leg.status, 'planned')

    # ------------------------------------------------------------------
    # Demurrage charge creation
    # ------------------------------------------------------------------

    def test_create_demurrage_charge(self):
        from datetime import date, timedelta
        self.env['freight.charge.type'].create({
            'name': 'Demurrage / Detention', 'code': 'DEM'})
        s = self._make_shipment(
            etd='2025-06-01', eta='2025-06-15', booking_ref='BK010')
        self.env['freight.container'].create({
            'name': 'TCKU9999999', 'shipment_id': s.id, 'container_type': '40hc'})
        s.action_book()
        s.action_in_transit()
        s.action_arrived()
        s.write({'date_arrived': date.today() - timedelta(days=20)})
        s._compute_demurrage()
        self.assertGreater(s.demurrage_days, 0)
        s.action_create_demurrage_charge()
        dem_charges = s.charge_ids.filtered(
            lambda c: c.charge_type_id.code == 'DEM')
        self.assertEqual(len(dem_charges), 1)
        self.assertGreater(dem_charges.amount, 0)

    def test_create_demurrage_charge_no_days_raises(self):
        s = self._make_shipment()
        with self.assertRaises(Exception):
            s.action_create_demurrage_charge()

    def test_create_demurrage_charge_duplicate_raises(self):
        from datetime import date, timedelta
        dem_type = self.env['freight.charge.type'].search(
            [('code', '=', 'DEM')], limit=1)
        if not dem_type:
            dem_type = self.env['freight.charge.type'].create({
                'name': 'Demurrage / Detention', 'code': 'DEM'})
        s = self._make_shipment(
            etd='2025-06-01', eta='2025-06-15', booking_ref='BK011')
        self.env['freight.container'].create({
            'name': 'TCKU8888888', 'shipment_id': s.id, 'container_type': '40hc'})
        s.action_book()
        s.action_in_transit()
        s.action_arrived()
        s.write({'date_arrived': date.today() - timedelta(days=20)})
        s._compute_demurrage()
        s.action_create_demurrage_charge()
        with self.assertRaises(Exception):
            s.action_create_demurrage_charge()

    # ------------------------------------------------------------------
    # Tariff deduplication
    # ------------------------------------------------------------------

    def test_tariff_apply_dedup(self):
        tariff = self.env['freight.tariff'].create({
            'name': 'Dedup Rate',
            'charge_type_id': self.charge_type.id,
            'origin_port_id': self.port_a.id,
            'destination_port_id': self.port_b.id,
            'shipping_line_id': self.shipping_line.id,
            'transport_mode': 'sea',
            'currency_id': self.env.company.currency_id.id,
            'rate': 500.0,
        })
        s = self._make_shipment()
        s.action_apply_tariff()
        self.assertEqual(len(s.charge_ids), 1)
        with self.assertRaises(Exception):
            s.action_apply_tariff()

    # ------------------------------------------------------------------
    # Cancelled shipment charge constraint
    # ------------------------------------------------------------------

    def test_charge_on_cancelled_shipment_raises(self):
        s = self._make_shipment()
        s.action_book()
        s.action_cancel()
        with self.assertRaises(Exception):
            self.env['freight.charge'].create({
                'shipment_id': s.id,
                'charge_type_id': self.charge_type.id,
                'name': 'Bad Charge',
                'amount': 100.0,
                'currency_id': self.env.company.currency_id.id,
            })

    # ------------------------------------------------------------------
    # ETA notification cron
    # ------------------------------------------------------------------

    def test_cron_eta_notifications(self):
        from datetime import date, timedelta
        target = date.today() + timedelta(days=3)
        s = self._make_shipment(
            etd='2025-06-01', eta=target.isoformat(),
            booking_ref='BK020')
        s.action_book()
        s.action_in_transit()
        self.assertFalse(s.eta_notification_sent)
        self.env['freight.shipment']._cron_eta_notifications()
        self.assertTrue(s.eta_notification_sent)

    def test_cron_eta_no_email_skipped(self):
        from datetime import date, timedelta
        target = date.today() + timedelta(days=3)
        no_email_customer = self.env['res.partner'].create({
            'name': 'No Email Customer'})
        s = self.env['freight.shipment'].create({
            **dict(self._base_vals),
            'customer_id': no_email_customer.id,
            'etd': '2025-06-01',
            'eta': target.isoformat(),
            'booking_ref': 'BK021',
        })
        s.action_book()
        s.action_in_transit()
        self.env['freight.shipment']._cron_eta_notifications()
        self.assertFalse(s.eta_notification_sent)
