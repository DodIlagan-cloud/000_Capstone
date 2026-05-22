# Contracts

<!-- M0 Foundation: explicit handoff boundary for shared module contracts. -->

Shared contracts belong here when a later module makes them concrete.

Initial contract families:

- `identity/`
- `documents/`
- `extraction/`
- `transactions/`

Contract changes should be owned by the module that defines the producer or consumer behavior and should be covered by module or integration tests.
