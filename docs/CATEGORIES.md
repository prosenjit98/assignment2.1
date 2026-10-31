# Category Definitions

<!-- Generated from data/categories.json by `python scripts/build_category_docs.py`. Do not edit by hand. -->

**Domain:** Internal Employee Service Desk. A single front door for employee requests. Every message is routed to the team that has to act on it: IT, Information Security, HR, Facilities or Finance.

## Summary

| Category | Routes to | Subcategories |
|---|---|---|
| IT Support | IT Service Desk | Hardware, Software, Network, Email & Collaboration, Accounts & Access, Printing |
| Information Security | Security Operations | Phishing & Suspicious Email, Malware & Virus, Account Compromise, Lost or Stolen Device, Data Exposure, Security Policy Question |
| HR | People Team | Payroll, Leave & Time Off, Benefits, Onboarding & Offboarding, Employee Relations, HR Policy & Documents |
| Facilities | Workplace Services | Building Access & Badges, Maintenance & Repairs, Workspace & Furniture, Health & Safety, Office Services |
| Finance | Finance Operations | Expenses & Reimbursement, Purchase Orders, Invoices & Vendor Payments, Corporate Card |
| Unclassified | Service Desk triage (human) | Needs Clarification, Out of Scope, Non-Actionable |

## IT Support

*Routes to: IT Service Desk.* Problems with, or requests for, company technology that do not put data at risk: devices, business software, network connectivity, email and collaboration tools, system accounts and printers.

| Subcategory | Covers |
|---|---|
| Hardware | Company laptops, desktops, monitors, docking stations, keyboards, mice, headsets and mobile phones: faults, damage, replacements and new equipment. |
| Software | Installing, licensing, updating or fixing business applications other than email and Teams, including applications owned by other departments (such as the expense or HR system) when the application itself is malfunctioning. |
| Network | Wi-Fi, wired network, VPN and internet connectivity, including slow or dropping connections. |
| Email & Collaboration | Outlook, mailboxes, calendars, Microsoft Teams, SharePoint and OneDrive sync problems. |
| Accounts & Access | Password resets, account lockouts, MFA setup, new system accounts and permission requests for applications, folders or shared drives. |
| Printing | Printers, scanners and copiers: jams, toner, print queues and printer setup. |

## Information Security

*Routes to: Security Operations.* Events that could put company data, accounts or systems at risk, and questions about security rules.

| Subcategory | Covers |
|---|---|
| Phishing & Suspicious Email | Suspicious emails, messages or calls trying to obtain credentials, money or data, whether or not the employee interacted with them. |
| Malware & Virus | Antivirus alerts, suspected viruses or ransomware, and unexpected software behaviour that suggests an infection. |
| Account Compromise | Signs that someone else is using an account: credentials entered on a suspicious site, MFA prompts the employee did not trigger, unknown sign-ins, files changed or deleted by someone else. |
| Lost or Stolen Device | Lost or stolen company laptops, phones, tablets or storage media. |
| Data Exposure | Sensitive data sent to the wrong recipient, shared publicly or accessed without authorisation. |
| Security Policy Question | Questions about security rules: approved tools, USB drives, password policy, data classification. |

## HR

*Routes to: People Team.* Employment, pay, leave, benefits and workplace conduct.

| Subcategory | Covers |
|---|---|
| Payroll | Salary, overtime, deductions, payslips, tax forms, and missing or incorrect pay. |
| Leave & Time Off | Vacation balances, sick leave, parental leave and leave requests. |
| Benefits | Health, dental, pension and other benefit plans, and enrolment. |
| Onboarding & Offboarding | The employment process for joiners, movers and leavers: contracts, start dates, payroll records and the overall readiness of a new hire. |
| Employee Relations | Harassment, discrimination, bullying, grievances and conflicts with colleagues or managers. |
| HR Policy & Documents | HR policies and employment documents: employment verification letters, contract copies, handbook questions. |

## Facilities

*Routes to: Workplace Services.* The physical workplace: buildings, physical access, maintenance, furniture, safety and office services.

| Subcategory | Covers |
|---|---|
| Building Access & Badges | Access badges, door readers, building entry, parking gates and visitor access. |
| Maintenance & Repairs | Heating, air conditioning, lighting, plumbing, leaks, broken doors and other building repairs. |
| Workspace & Furniture | Desks, chairs, ergonomic equipment, desk moves and meeting room setup. |
| Health & Safety | Fire, smoke, gas smells, electrical hazards, injuries, spills and anything else that could hurt someone. |
| Office Services | Kitchens and coffee machines, cleaning, office supplies, mail and deliveries. |

## Finance

*Routes to: Finance Operations.* Company money: expenses, purchasing, supplier payments and corporate cards.

| Subcategory | Covers |
|---|---|
| Expenses & Reimbursement | Expense claims, reimbursement status and expense policy questions. |
| Purchase Orders | Requests to raise, change or approve purchase orders and purchase requisitions. |
| Invoices & Vendor Payments | Supplier invoices, payment status and vendor payment issues. |
| Corporate Card | Company credit cards: declines, limits, lost cards and card statements. |

## Unclassified

*Routes to: Service Desk triage (human).* Use only when the message cannot be routed to any team above.

| Subcategory | Covers |
|---|---|
| Needs Clarification | Too vague, incomplete or garbled to route; a follow-up question is needed. |
| Out of Scope | Not a workplace service request: general knowledge, personal errands, chit-chat. |
| Non-Actionable | Nothing to act on: thank-you notes, FYIs, auto-replies, spam. |

## Priority levels

| Priority | Response target | When to use |
|---|---|---|
| Critical | 15 minutes | Immediate danger to people; a confirmed security compromise in progress (someone else using an account, credentials entered on a phishing site, spreading malware, sensitive data confirmed exposed outside the company); or an outage stopping many people, a whole team or site, or a business-critical system. |
| High | 4 business hours | One person or a small group fully blocked with no workaround; a hard deadline within about 24 hours; or serious exposure such as a lost or stolen device, pay not received, a harassment or discrimination report, or a supplier threatening to stop service. |
| Medium | 1 business day | Work is degraded or inconvenient but a workaround exists; standard requests needed within days; contained security events (a phishing email reported but not clicked, malware already quarantined). |
| Low | 3 business days | Questions, how-tos, information requests, cosmetic issues and requests with no near-term deadline. |

Priority is judged by described impact and urgency, never by tone: "URGENT!!!" on a minor issue stays Low,
and a serious risk described casually still gets the priority its impact deserves.

## Overlap rules

When a message could belong to more than one category:

1. Route to the team that must act to resolve the request. A malfunctioning application is IT Support / Software even when another department owns the process: the expense tool crashing is IT Support, a question about what can be expensed is Finance.
2. Anything that may put company data or accounts at risk is Information Security, even when hardware or access is involved: a lost laptop is Information Security / Lost or Stolen Device, not IT Support / Hardware.
3. Physical access (badges, doors, gates) is Facilities; access to systems, applications or files is IT Support / Accounts & Access.
4. Fire, smoke, gas, electrical hazards, injuries or other danger to people is always Facilities / Health & Safety at Critical priority, however casually it is described.
5. New joiners and leavers: use HR / Onboarding & Offboarding when the employment process is involved (contracts, start dates, payroll records), even if equipment or accounts are also missing, and list IT Support as a secondary category. Use IT Support alone when the request is only about equipment or accounts.
6. Computer peripherals (keyboards, mice, monitors, headsets) are IT Support / Hardware; furniture and ergonomics are Facilities / Workspace & Furniture; consumables and supplies are Facilities / Office Services.
7. If a message contains several requests, classify it by the most severe or urgent one and list the other teams in secondary_categories.
