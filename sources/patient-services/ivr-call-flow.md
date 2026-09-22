# QuorvantaConnect IVR call flow (fictitious)

> Everything here is invented. QuorvantaConnect, its phone menus and every prompt do not exist. Job code AQB-QC-IVR-0926, v1.0. Each prompt is followed by the approved patient-services responses (`PSR-*`), fixed messages (`ps_*`) or escalation rules (`ESC-*`) that support it.

Inbound number 1-800-555-0183. Prompts are recorded in English and Spanish; option 9 on the language menu reaches an interpreter line during program hours.

## IVR-00 Language

"Thank you for calling QuorvantaConnect. For English, press 1. Para español, oprima 2. For another language, press 9."

## IVR-01 Greeting and safety

"If this is a medical emergency, hang up and call 911." `[ps_emergency]`

"To report a side effect of QUORVANTA, press 8 at any time to reach Arden Quay Biosciences Drug Safety." `[ESC-01]`

## IVR-02 Hours check

During program hours, go to IVR-03.

Outside program hours: "QuorvantaConnect case managers are available Monday through Friday, 8 a.m. to 8 p.m. Eastern Time. If you leave your name and number, someone will call you back the next business day. If you think you're having a side effect, you can call Drug Safety at 1-800-555-0142." `[ps_after_hours]` Then go to voicemail.

## IVR-03 Main menu

"If you're a patient or calling for a patient, press 2. If you're calling from a healthcare provider's office, press 3. If you're calling from a pharmacy, press 4. For general information about QuorvantaConnect, press 5."

- 2: go to IVR-04.
- 3: route to the prescriber office queue. Prescriber offices are not handled by the patient-services assistant (conversation-rules.json, role prescriber_office).
- 4: route to the pharmacy liaison queue.
- 5: go to IVR-06.

## IVR-04 Patient identification

"To help protect your privacy, we'll confirm who we're speaking with before we discuss a case. Please enter the patient's date of birth as eight digits, month, day and year." `[PSR-080]`

"Now enter the patient's five-digit ZIP code, or press star to enter the case number instead." `[VER]`

The IVR matches the date of birth and ZIP code or case number, then a case manager confirms the patient's full name before discussing the case. After three failed attempts: `[ps_verification_failed]`, then transfer to a case manager, who repeats verification.

## IVR-05 Patient menu (after identification)

"For questions about insurance, a prior authorization or an appeal, press 1. For the copay program or other financial help, press 2. For questions about a delivery or refill, press 3. To talk with a nurse about taking QUORVANTA, press 4. For anything else, press 0."

- 1 and 2: case manager queue.
- 3: "Your specialty pharmacy handles questions about a particular delivery, delivery dates and replacements. We can give you their number, or contact them for you." `[PSR-064]` Press 1 to transfer to the pharmacy on file, or 2 for a case manager.
- 4: nurse queue. "QuorvantaConnect nurses can talk with you by phone about how to take QUORVANTA and what to expect in the first months, including flushing and stomach upset. They can't give medical advice, tell you whether a symptom is serious, or change your dose; those questions go to your healthcare provider." `[PSR-070]`
- 0: case manager queue. `[ps_human_transfer]`

## IVR-06 General information

"QuorvantaConnect is a free support program from Arden Quay Biosciences for adults who have been prescribed QUORVANTA. It can help with insurance, the copay program, getting your prescription to the right specialty pharmacy, and questions about taking QUORVANTA." `[PSR-001]`

"You can enroll through the QUORVANTA Start Form your healthcare provider sends, at quorvantaconnect.example, or by calling 1-800-555-0183. You can choose the services you want and skip the ones you don't." `[PSR-003]`

"If your insurance is commercial or through an employer, including plans from a health insurance marketplace, you may pay as little as $0 a month for QUORVANTA. The program pays up to $16,000 a year. It isn't available to anyone enrolled in Medicare, Medicaid, TRICARE, the VA or another government health program, even if they also have commercial insurance." `[PSR-020]`

"To speak with someone, press 0." `[ps_human_transfer]`

## IVR-07 Hold message

"QuorvantaConnect can't give medical advice. Questions about whether QUORVANTA is right for you, about symptoms, or about changing your dose are for your healthcare provider." `[PSR-005]`

"You can send documents, such as your insurance card, income documents or receipts, through quorvantaconnect.example or by fax to 1-800-555-0184." `[PSR-008]`
