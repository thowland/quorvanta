# QuorvantaConnect benefits and assistance letter templates (fictitious)

> Everything here is invented. QuorvantaConnect, the Arden Quay Patient Assistance Foundation and every letter, amount and timeline do not exist. Placeholders in `{{double braces}}` are filled from the case record (field paths as in `test-design/ps-cases.json`). Each statement is followed by the approved patient-services responses (`PSR-*`) or case statuses that support it.

Letters are sent by the contact method the patient chose on the Start Form. Each letter carries the footer in L-00.

## L-00 Footer on every letter

QuorvantaConnect: 1-800-555-0183, Monday through Friday, 8 a.m. to 8 p.m. Eastern Time. Fax 1-800-555-0184. quorvantaconnect.example. `[PSR-002]`

QuorvantaConnect can't give medical advice. Please talk to your healthcare provider about your treatment. `[PSR-005]`

To report a side effect, call Arden Quay Biosciences Drug Safety at 1-800-555-0142 or FDA at 1-800-FDA-1088.

## L-01 Benefits summary for the patient

*Job code AQB-QC-BVP-0926.*

Dear {{patient.first_name}},

We've checked with {{insurance.plan_name}} about your coverage for QUORVANTA. This is what your plan told us on {{bv.completed_on}}. Your plan makes the final decision on coverage. `[PSR-011]`

- Coverage: {{bv.status_text}} `[PSR-101]`
- Prior authorization: {{pa.status_text}} `[PSR-102]`
- Required pharmacy: {{pharmacy.name}}, {{pharmacy.phone}} `[PSR-110]`
- Expected cost for a 30-day supply, before any copay help: ${{bv.expected_cost_share}} `[PSR-103]`

QuorvantaConnect doesn't make coverage decisions, and we can't promise or predict what your plan will decide. `[PSR-015]`

If your insurance is commercial or through an employer, you may pay as little as $0 a month through the copay program, up to $16,000 a year. It isn't available to anyone enrolled in Medicare, Medicaid, TRICARE, the VA or another government health program. `[PSR-020]`

Your case number is {{case_id}}, and your case manager is {{case_manager}}. `[PSR-100]`

## L-02 Benefits summary for the prescriber's office

*Job code AQB-QC-BVH-0926. Sent by fax to the office on file.*

Re: {{patient.first_name}} {{patient.last_name}}, date of birth {{patient.dob}}. QuorvantaConnect case {{case_id}}.

Benefits verification completed {{bv.completed_on}} with {{insurance.plan_name}}. The information below is as reported by the plan; the plan makes the final coverage determination. `[PSR-011]`

- Coverage status: {{bv.status}}
- Prior authorization status: {{pa.status}}
- Plan-required pharmacy: {{pharmacy.name}} ({{pharmacy.id}})
- Patient cost-share per 30-day supply, per plan: ${{bv.expected_cost_share}}
- Copay program: {{copay.status}}
- Bridge supply: {{bridge.status}}

If prior authorization is required, QuorvantaConnect will prepare the request for your signature and submit it the same business day it is signed. `[PSR-012]`

Case manager: {{case_manager}}, 1-800-555-0183.

## L-03 Prior authorization decision: not approved

*Job code AQB-QC-PAD-0926.*

Dear {{patient.first_name}},

{{pa.status_text}} `[PSR-102]`

We'll explain the reason your plan gave. We've also given your healthcare provider's office an appeal letter template and a list of what your plan needs. Your healthcare provider decides whether to appeal. `[PSR-014]`

QuorvantaConnect doesn't make coverage decisions, and we can't promise or predict what your plan will decide. `[PSR-015]`

If your coverage is delayed while an appeal is pending, you may be able to get QUORVANTA at no cost while you wait. Bridge supply is for people with commercial or employer insurance who meet the copay program's rules. `[PSR-030]`

## L-04 Copay program welcome

*Job code AQB-QC-CPW-0926.*

Dear {{patient.first_name}},

Welcome to the QuorvantaConnect copay program. If your insurance is commercial or through an employer, including plans from a health insurance marketplace, you may pay as little as $0 a month for QUORVANTA. The program pays up to $16,000 a year. It isn't available to anyone enrolled in Medicare, Medicaid, TRICARE, the VA or another government health program, even if they also have commercial insurance. `[PSR-020]`

You don't need a card. Your specialty pharmacy applies the copay program automatically. `[PSR-023]`

The program pays up to $16,000 a year. Once it has paid that amount, you pay what your plan charges for the rest of the year. The amount starts over on January 1. `[PSR-021]`

Some plans don't count copay program payments toward your deductible or out-of-pocket maximum. The program still pays up to its yearly limit, but your deductible may not go down, and you may owe more later in the year. Your case manager can explain how your plan handles this. `[PSR-025]`

Your enrollment runs through {{copay.enrolled_through}}. You need to re-enroll each year, and we'll send you a reminder in November. `[PSR-105, PSR-026]`

Please tell QuorvantaConnect within 30 days if your insurance changes, including if you enroll in Medicare. Copay program benefits end on the date you're no longer eligible. `[PSR-027]`

The copay program isn't insurance, and you can't ask anyone else to repay you for what the program covers. `[PSR-028]`

## L-05 Foundation application incomplete

*Job code AQB-QC-PAI-0926.*

Dear {{patient.first_name}},

Your application to the Arden Quay Patient Assistance Foundation still needs: {{pap.missing_documents}}. The Foundation decides within 5 business days once it has everything. `[PSR-108]`

Proof of household income can be your latest federal tax return, two recent pay stubs, a benefits award letter, or a signed statement that you have no income. If you have insurance, include your plan's denial. `[PSR-042]`

You can send documents, such as your insurance card, income documents or receipts, through quorvantaconnect.example or by fax to 1-800-555-0184. `[PSR-008]`

## L-06 Foundation approval

*Job code AQB-QC-PAA-0926.*

Dear {{patient.first_name}},

{{pap.status_text}} `[PSR-107]`

Tigerwater Specialty Pharmacy will send QUORVANTA to you in 30-day supplies, with nothing to pay. `[PSR-040]`

Foundation approval lasts 12 months. You'll need to re-apply with updated income documents before it ends; we'll remind you 60 days ahead. `[PSR-044]`
