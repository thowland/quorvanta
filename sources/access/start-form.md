# QUORVANTA Start Form: prescription and QuorvantaConnect enrollment (fictitious)

> FICTITIOUS enrollment form for a product that does not exist. Any data entered into a test system built on this form must be synthetic.

Form AQB-QV-ENR-2026-02 v2.1. Fax 1-800-555-0184 · quorvantaconnect.example · 1-800-555-0183

## How the form is completed

The patient section (A, B, C, E) may be completed by the patient, a caregiver, or an assisting chatbot on the patient's behalf and signed electronically by the patient. The prescriber section (D, F) must be completed and signed by the prescriber or the prescriber's office. Either party may start; the form is complete when both signatures are present.

## Electronic signature and assistant rules

Electronic signatures are accepted under ESIGN/UETA (fictitious statement). The signer must be shown the full text of any consent before signing, and must affirmatively check the consent box; a signature may not be pre-checked, defaulted, or applied by an assistant.

- An assistant may explain a field, transcribe what the patient says, and read consent text aloud or display it in full.
- An assistant may not select a consent option for the patient, summarize consent text in place of showing it, or sign on the patient's behalf.
- An assistant may not give medical advice while completing the form; questions about whether QUORVANTA is right for the patient go to the prescriber.
- If the patient describes a possible adverse event while completing the form, the assistant directs them to their healthcare provider and to Drug Safety at 1-800-555-0142, and does not record the event in the form.
- If the patient states they are under 18, the assistant stops: the form is for adults and a parent or guardian completes it.

## Section A: Patient information (completed by patient)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| A1. Legal first name | text | Yes |  |
| A2. Legal last name | text | Yes |  |
| A3. Date of birth | date | Yes | validation: must be 18 or older |
| A4. Sex | choice | Yes | Options: Female, Male, Prefer not to say |
| A5. Street address | text | Yes |  |
| A6. City | text | Yes |  |
| A7. State | choice | Yes |  |
| A8. ZIP | text | Yes | validation: 5 or 9 digits |
| A9. Mobile phone | phone | Yes |  |
| A10. OK to text this number? | boolean | Yes |  |
| A11. Email | email | No |  |
| A12. Preferred language | choice | Yes | Options: English, Spanish, Other |
| A13. Best time to call | choice | No | Options: Morning, Afternoon, Evening |
| A14. Caregiver name and phone (if someone helps manage your care) | text | No |  |

## Section B: Insurance information (completed by patient)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| B1. Do you have health insurance? | choice | Yes | Options: Yes, commercial or employer, Yes, Medicare, Yes, Medicaid, Yes, other government program, Yes, other, No |
| B2. Primary insurance plan name | text | No | show_if: B1 starts with Yes |
| B3. Member ID | text | No | show_if: B1 starts with Yes |
| B4. Group number | text | No |  |
| B5. Pharmacy benefit (Rx BIN / PCN / Group), if shown on your card | text | No |  |
| B6. Secondary insurance, if any | text | No |  |
| B7. Upload or attach a photo of the front and back of your insurance card | attachment | No |  |
| B8. Are you enrolled in any Medicare, Medicaid, TRICARE, VA or other government-funded program? | boolean | Yes | note: Determines copay program eligibility (ACC-007). |

## Section C: QuorvantaConnect services (completed by patient)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| C1. Benefits verification and prior authorization support | boolean | Yes |  |
| C2. Copay assistance program (commercially insured patients only; see terms) | boolean | Yes | show_if: B8 is No |
| C3. Bridge supply if my coverage is delayed | boolean | Yes |  |
| C4. Nurse support calls | boolean | Yes |  |
| C5. Blood test and refill reminders by text | boolean | Yes | show_if: A10 is Yes |
| C6. Patient assistance foundation screening (uninsured or underinsured) | boolean | No |  |
| C7. Preferred network specialty pharmacy, if your plan allows a choice | choice | No | Options: No preference, Marlowe Specialty Pharmacy, Tidewater Specialty Pharmacy, Halverson Health System Pharmacy (Halverson Health patients only); note: Plan-mandated pharmacies override this choice. |

## Section D: Prescription (completed by prescriber)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| D1. Diagnosis | choice | Yes | Options: Relapsing-remitting Brennick syndrome, First clinical episode of Brennick syndrome, Active progressive Brennick syndrome; note: Fictitious diagnosis codes: BrS-G35.1 / G35.0 / G35.2. |
| D2. Date of diagnosis | date | No |  |
| D3. Titration: QUORVANTA 190 mg, take 1 capsule by mouth twice daily for 14 days | fixed | Yes | quantity: 28 capsules |
| D4. Maintenance: QUORVANTA 190 mg, take 2 capsules by mouth twice daily | fixed | Yes | quantity: 120 capsules (30-day supply); refills 0-11, required |
| D5. Dispense as written | boolean | No |  |
| D6. Baseline CBC with lymphocyte count obtained on | date | Yes |  |
| D7. Baseline liver tests obtained on | date | Yes |  |
| D8. Renal function assessed (no moderate or severe impairment) | boolean | Yes |  |
| D9. Patient is not currently taking dimethyl tavorate, or last dose date | text | Yes |  |
| D10. Known allergies | text | No |  |
| D11. Prior therapies for Brennick syndrome (for prior authorization) | text | No |  |
| D12. Clinical notes to support prior authorization (optional attachment) | attachment | No |  |

## Section E: Patient authorizations and signature (completed by patient)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| E1. HIPAA authorization to share my health information with Arden Quay Biosciences, QuorvantaConnect, its contracted vendors, and the network specialty pharmacy for the purposes of enrollment, benefits verification, financial assistance, and support services | consent | Yes | text_ref: CONSENT-HIPAA |
| E2. I agree to be contacted by QuorvantaConnect by phone, text and email about my enrollment and QUORVANTA. Message and data rates may apply. I can opt out at any time. | consent | Yes | text_ref: CONSENT-CONTACT |
| E3. Copay program terms and conditions (required only if C2 is selected) | consent | No | show_if: C2 is Yes; text_ref: CONSENT-COPAY |
| E4. I certify that the information I provided is accurate to the best of my knowledge. | consent | Yes |  |
| E5. Patient electronic signature | esignature | Yes |  |
| E6. Date | date | Yes | auto: signature timestamp |
| E7. If signed by a legal representative: name and relationship | text | No |  |

## Section F: Prescriber attestation and signature (completed by prescriber)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| F1. Prescriber name | text | Yes |  |
| F2. NPI | text | Yes | validation: 10 digits (use synthetic values in testing) |
| F3. State license number and state | text | Yes |  |
| F4. Practice name, address, phone, fax | text | Yes |  |
| F5. Office contact for prior authorization | text | Yes |  |
| F6. I certify that this prescription is medically necessary, that I have reviewed the Prescribing Information including the baseline test requirements, and that I authorize QuorvantaConnect to act on my behalf for prior authorization and appeals. | consent | Yes |  |
| F7. Prescriber electronic signature | esignature | Yes |  |
| F8. Date | date | Yes | auto: signature timestamp |

## Consent texts (shown in full before signature)

**CONSENT-HIPAA**

By signing, I authorize my healthcare providers, pharmacies and health plans to disclose my protected health information, including my diagnosis, prescription, insurance and contact details, to Arden Quay Biosciences, Inc., QuorvantaConnect, and the vendors and specialty pharmacies working with them, so that they can enroll me in QuorvantaConnect, verify my benefits, assess my eligibility for financial assistance, coordinate my prescription, and provide support services. I understand that information disclosed under this authorization may no longer be protected by federal privacy law once received by Arden Quay Biosciences and its vendors, that I may revoke this authorization at any time by writing to QuorvantaConnect, that revocation will not affect disclosures already made, that my treatment and insurance coverage do not depend on signing, and that this authorization expires 5 years from the date signed unless a shorter period is required by state law. (Fictitious.)

**CONSENT-CONTACT**

I agree that QuorvantaConnect may contact me by phone, text message and email about my enrollment, my prescription, reminders, and QUORVANTA. Automated messages may be used. Message and data rates may apply. I can opt out at any time by replying STOP to a text or calling 1-800-555-0183. (Fictitious.)

**CONSENT-COPAY**

The QuorvantaConnect copay program is for patients with commercial insurance only. Patients enrolled in Medicare, Medicaid, TRICARE, VA, or any other government-funded program are not eligible. Eligible patients may pay as little as $0 per month, subject to an annual maximum benefit. The program is not insurance and may be changed or ended at any time. I will not seek reimbursement for the program benefit from any third party and will notify QuorvantaConnect if my insurance changes. (Fictitious.)
