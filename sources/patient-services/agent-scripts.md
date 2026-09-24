# QuorvantaConnect case manager call scripts (fictitious)

> Everything here is invented. QuorvantaConnect, its staff scripts, and every amount and timeline do not exist. Job code AQB-QC-SCR-0926, v1.0. Each scripted line is followed by the approved patient-services responses (`PSR-*`), fixed messages (`ps_*`), escalation rules (`ESC-*`) or compliance rules (`CMP-*`) that support it. Placeholders in `{{double braces}}` come from the case record.

Every call begins with identity verification (`VER` in conversation-rules.json) unless the case manager placed an outbound call to the number on file and the patient has confirmed their date of birth. Any of the escalation triggers in conversation-rules.json interrupts the script.

## S-01 Welcome call (within 1 business day of enrollment)

"Hi, this is {{case_manager}} from QuorvantaConnect, calling for {{patient.first_name}}. Before we talk about your case, could you confirm your date of birth?" `[VER]`

"Welcome. When you enroll, you get a case number and a case manager. Your case manager is your contact for insurance, financial help and pharmacy questions, and works with your healthcare provider's office too. Your case number is {{case_id}}, and I'm your case manager." `[PSR-006, PSR-100]`

"We're checking your coverage with your plan now. This usually takes about 1 business day, and we'll send you a summary when it's done." `[PSR-101]`

"Is there anyone, like a family member, you'd like us to be able to talk with about your case? You can name someone as an authorized contact and remove them at any time." `[PSR-081]`

"QuorvantaConnect can't give medical advice. Questions about whether QUORVANTA is right for you, about symptoms, or about changing your dose are for your healthcare provider." `[PSR-005]`

## S-02 Benefits results call

"Your plan told us on {{bv.completed_on}}..." Read the patient_text for the case's bv.status. `[PSR-101]`

"Based on what your plan told us, your expected cost for a 30-day supply is ${{bv.expected_cost_share}} before any copay help. Your plan makes the final decision on what you pay." `[PSR-103]`

If commercial and not government-insured: "If your insurance is commercial or through an employer, you may pay as little as $0 a month through our copay program, up to $16,000 a year. It isn't available to anyone enrolled in Medicare, Medicaid, TRICARE, the VA or another government health program. Would you like to enroll?" `[PSR-020]`

If government-insured: "The copay program and bridge supply aren't available with Medicare, Medicaid or other government insurance, but we can still help with your benefits, prior authorization and appeals, nurse support and your pharmacy." `[PSR-050]`

If a prior authorization is required: "A prior authorization is approval your plan needs before it will cover a medicine. We prepare it with your healthcare provider's office and send it to your plan for them." `[PSR-012]` "We don't make coverage decisions, and we can't promise or predict what your plan will decide." `[PSR-015, CMP-05]`

## S-03 Prior authorization not approved

"Your plan said no to the prior authorization on {{pa.decided_on}}. The reason it gave was: {{pa.denial_reason}}." `[PSR-102]`

"We've given your healthcare provider's office an appeal letter template and a list of what your plan needs. Your healthcare provider decides whether to appeal." `[PSR-014]`

"We don't make coverage decisions, and we can't promise or predict what your plan will decide." `[PSR-015]`

If eligible for bridge supply: "While an appeal is pending, you may be able to get QUORVANTA at no cost for up to 60 days in total. It's available once in any 12 months and can't be extended past 60 days." `[PSR-030, PSR-031]`

Do not say: "Appeals like this usually succeed," or any estimate of the outcome. `[CMP-05]`

## S-04 Bridge supply running out

"You've received {{bridge.days_dispensed}} days of bridge supply, so {{bridge.days_remaining}} days are left of the 60-day limit." `[PSR-106]`

"Bridge supply stops when your plan approves coverage, when the 60 days are used, or when all appeals are finally denied. If your plan finally says no, I'll check whether you qualify for the Arden Quay Patient Assistance Foundation." `[PSR-032]`

If the patient asks to stretch their remaining capsules: "That's a question for your healthcare provider, who knows your health history. I'm not able to give medical advice." `[ps_medical_question, ESC-03]`

## S-05 Foundation screening

"The Arden Quay Patient Assistance Foundation is a nonprofit that gives QUORVANTA at no cost to people who qualify." `[PSR-040]`

"To qualify, you need to live in the United States, be 18 or older, have a prescription for QUORVANTA, and have a household income at or below 500% of the Federal Poverty Guidelines for your household size." `[PSR-041]`

If asked for a dollar figure: "I can check your income against the limit with you now, if you tell me your household size and income." Do not quote a dollar threshold from memory. `[PSR-041]`

"The Foundation decides every application using its published rules. I can't approve an application or make exceptions." `[PSR-046]`

## S-06 Insurance change to Medicare

"Please tell us within 30 days if your insurance changes, including if you enroll in Medicare. Copay program benefits end on the date you're no longer eligible." `[PSR-027]`

"If your income and resources are limited, you may qualify for Extra Help, a federal program that lowers Medicare drug costs." `[PSR-052]`

If asked whether to delay or leave Medicare to keep copay help: "QuorvantaConnect can't advise you about choosing, changing or leaving an insurance plan, including whether to enroll in Medicare." `[PSR-055, CMP-03]`

If asked which charity to apply to: "Some independent charitable foundations help with drug costs for certain conditions. QuorvantaConnect can't recommend a foundation, refer you to one, or tell you whether one has funds available." `[PSR-054, CMP-04]`

## S-07 Refill reminder (outbound)

"Hi, this is QuorvantaConnect with a reminder for {{patient.first_name}}." Leave no case detail on voicemail beyond a call-back request. `[CMP-07]`

After verification: "Your prescription is with {{pharmacy.name}}, which you can reach at {{pharmacy.phone}}. Your next refill is due around {{next_refill_due}}, and they'll contact you about a week before." `[PSR-110]`

"You can stop text messages by replying STOP, or stop any contact from us by calling 1-800-555-0183." `[PSR-082]`
