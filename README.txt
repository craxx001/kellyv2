FF GLOBAL STORE
================

Updated dashboard/store frontend:
- Main branding: FF GLOBAL STORE
- Removed visible Binance promotion
- Replaced the header access pill with Guild Glory / Autolike service tabs
- Added Guild Glory plans and Autolike plans with requested prices/details
- Autolike Gold and Diamond are marked Out of Stock and disabled
- Removed the visible level-up start/running/levels-gained UI from the store surface
- Removed Buy Time from the menu
- Header timer is kept as the service-plan timer; slot pill is removed
- Added Running Plans UI with countdown timers using browser storage for the current frontend prototype

Important:
The new Buy Now buttons currently create a local Running Plan entry for frontend testing. A real payment/checkout endpoint for Guild Glory and Autolike was not provided in the source, so the existing level-pass payment endpoint was intentionally NOT reused for these new services.

Deploy index.html with assets/index.js and assets/index.css.
