export const demoStats = {
  total_inspections: 4,
  compliant: 2,
  non_compliant: 1,
  review: 1,
  compliance_rate: 50,
  recent_alerts: 2
}

export const demoInspections = [
  {
    inspection_id: 'SYN-DEMO-1042',
    user_id: 'demo-user',
    created_at: '2026-09-10T10:30:00+05:30',
    product: { name: 'Harvest Gold Rice', category: 'Food & beverage' },
    fields: { generic_name: 'Basmati rice', net_quantity: '1 kg', mrp: 'Rs 145.00', manufacturer: 'Harvest Gold Foods Pvt. Ltd.' },
    visual_checks: { readability: 'Clear', font_height: 1.5, placement: 'Compliant' },
    compliance: { status: 'PASS', score: 0.96, confidence: 0.94, violations: [] },
    rules_obeyed: ['Product name declaration', 'Net quantity declaration', 'MRP declaration', 'Manufacturer details'],
    rules_not_obeyed: []
  },
  {
    inspection_id: 'SYN-DEMO-1039',
    user_id: 'demo-user',
    created_at: '2026-09-09T14:15:00+05:30',
    product: { name: 'FreshSip Mango Drink', category: 'Food & beverage' },
    fields: { generic_name: 'Mango beverage', net_quantity: '750 ml', mrp: 'Rs 80.00', manufacturer: 'FreshSip Beverages' },
    visual_checks: { readability: 'Clear', font_height: 1.2, placement: 'Compliant' },
    compliance: { status: 'FAIL', score: 0.78, confidence: 0.92, violations: ['Expiry date missing', 'Required declaration unreadable'] },
    rules_obeyed: ['Product name declaration', 'Net quantity declaration', 'MRP declaration'],
    rules_not_obeyed: [{ rule: 'Expiry date declaration', reason: 'No readable expiry date was detected.' }, { rule: 'Required declaration readability', reason: 'One mandatory declaration could not be read clearly.' }]
  },
  {
    inspection_id: 'SYN-DEMO-1035',
    user_id: 'demo-user',
    created_at: '2026-09-08T11:05:00+05:30',
    product: { name: 'PureCare Handwash', category: 'Personal care' },
    fields: { generic_name: 'Liquid handwash', net_quantity: '250 ml', mrp: 'Rs 110.00' },
    visual_checks: { readability: 'Fair', font_height: 0.9, placement: 'Review needed' },
    compliance: { status: 'REVIEW', score: 0.68, confidence: 0.81, violations: ['Manufacturer address needs review'] },
    rules_obeyed: ['Product name declaration', 'Net quantity declaration', 'MRP declaration'],
    rules_not_obeyed: [{ rule: 'Manufacturer details', reason: 'Address text requires manual confirmation.' }]
  }
]
