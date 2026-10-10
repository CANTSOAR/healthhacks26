# Hospital and teaching knowledge

The hospital domain connects patient journeys, clinical knowledge, people, resources, community services, finance and learning. Facts, reported perspectives, assumptions and teaching scenarios retain their distinct meanings.

## Language

### Place and people

**Facility**: A care delivery establishment with a defined legal or reporting scope.
_Avoid_: Campus, health system, service unit

**Physical location**: A campus, building, wing, floor, room or bed space with physical containment and adjacency.
_Avoid_: Department when its meaning is organizational

**Service unit**: An organizational service or team that can operate across multiple physical locations.
_Avoid_: Wing, floor

**Resource**: An individually tracked reusable asset whose availability constrains service.
_Avoid_: Physical capacity when describing current availability

**Capacity snapshot**: A count at a stated time and scope, explicitly distinguished as licensed, physical, staffed, available, occupied, blocked or surge capacity.
_Avoid_: Beds without a capacity basis

**Role assignment**: A person acting in a specified role for an organization during a stated period.
_Avoid_: Doctor identity as a substitute for role or authority

**Privilege**: An explicit grant of authority for a person or role to perform scoped activities at a facility.
_Avoid_: Affiliation, specialty, shift

**Shift**: A planned or actual interval of availability for a role assignment.
_Avoid_: Provider directory listing

### Care and information

**Patient journey**: Linked care encounters and transitions experienced by one patient across settings.
_Avoid_: Encounter when the journey spans multiple encounters

**Encounter**: A bounded care interaction with a patient in a defined setting.
_Avoid_: Case, scenario

**Assertion**: An attributed statement about a subject with explicit origin, state, context and evidence.
_Avoid_: Truth when the statement is unverified or reported

**Observation**: A time-specific measurement or finding with its method and interpretation context.
_Avoid_: Diagnosis

**Perspective**: A reported or explicitly authored belief, goal, concern, preference or barrier.
_Avoid_: Objective clinical finding

**Activity definition**: The reusable meaning and requirements of a procedure, diagnostic test, consultation or support activity.
_Avoid_: Procedure instance, billing code

**Order**: A request to perform an activity.
_Avoid_: Completed procedure

**Activity performance**: An actual or simulated execution of an activity, including cancelled or incomplete attempts.
_Avoid_: Order, procedure code

**Explicit absence**: A finding that was actually reported or established as absent.
_Avoid_: Unknown, pending, missing

### Money and population

**Coverage**: Patient-specific enrollment and eligibility information for an insurance plan during a defined period.
_Avoid_: Accepted insurance, guaranteed payment

**Network participation**: Dated participation of a facility or professional for a particular plan and service scope.
_Avoid_: Coverage

**Authorization**: A payer's scoped decision concerning a requested service.
_Avoid_: Payment guarantee

**Charge**: A billed or published charge amount for a specified component of service.
_Avoid_: Cost, reimbursement, patient liability

**Resource cost**: The attributed cost of providing resources or services under a stated accounting method.
_Avoid_: Price, charge

**Patient liability**: An amount the patient is determined to owe within a specified coverage and adjudication context.
_Avoid_: Hospital list price

**Population definition**: Explicit membership criteria, geographic scope, period and denominator for a cohort.
_Avoid_: Catchment inferred solely from a hospital address

### Learning, evidence and simulation

**Source record**: A versioned source artifact or snapshot with retrieval, attribution and reuse context.
_Avoid_: Approved knowledge

**Case version**: An immutable authored patient scenario with explicitly enumerated facts and disclosure rules.
_Avoid_: Real patient record, live encounter

**Scenario template**: A reusable teaching situation with learning objectives, permissible variation and completion criteria.
_Avoid_: Generated patient facts

**Disclosure rule**: A rule controlling when an audience may discover a case fact.
_Avoid_: Rule that changes the underlying fact

**Review decision**: A decision about an exact version and use scope by an identified reviewer.
_Avoid_: Universal approval

**Parameter**: A numeric value or distribution with applicability, unit, uncertainty and dependency context.
_Avoid_: Local measurement when the value is assumed or externally benchmarked

**Qualitative finding**: An attributed theme, experience, exception or practice tied to a method and population context.
_Avoid_: Universal behavior probability

**Validation study**: A scoped comparison with suitable independent evidence and explicit acceptance criteria.
_Avoid_: Visual realism, successful parsing
