# Story #1 — Responsive English marketplace website

## Source and scope

Backlog: first story under **Platform foundation**, estimate 8.
Primary requirements: UI-002, UI-003, UI-005, UI-006, NFR-PORT-001,
NFR-USE-001, NFR-USE-002. Stack: SRS §2.6.

The initial delivery establishes an English responsive interface and a monorepo
baseline. Guests can navigate the public presentation without authentication.
Search and live public listings remain story #7; filters and sorting remain #11.
Accounts (#3–6), listing creation/management, chat, and order/payment actions have
their own stories. UI-003 is therefore only partially fulfilled by this delivery:
guest access to the shell is ready, while real browsing/search requires #7.

Pages:

- `/`: marketplace home, six internet-ad categories, example cards, explanatory sections.
- `/listings`: six clearly labeled example offers/requests, one for every category.
- `/listings/[slug]`: sample details and placement specifications, disabled contact actions.
- `/orders`: order-area preview linking to a read-only example.
- `/orders/demo`: sample layout for stages, requirements, materials, and summary.
- `/how-it-works`: customer/provider introduction consistent with the SRS.
- Unknown routes/listings: meaningful HTTP 404 with navigation back to the marketplace.

Only UI interactions are implemented: navigation, mobile menu, anchor links, and
keyboard support. No sign-in session, funds, orders, phone numbers, or emails are
created or exposed. Demo routes are not an authorization pattern for future real
orders. Future order routes must enforce participant/staff access on the backend.

Basic Docker and CI files support the requested project initialization. Story #51
also requires repository settings, project board setup, and deployment work;
those external acceptance items are not completed by these local files.

## Automated acceptance

Run:

```sh
just check
npm run test:e2e:install
just e2e
docker compose up --build --wait
```

The Playwright suite checks all six pages at 320, 360, 768, and 1440 px in Chromium,
Firefox, and WebKit. It asserts no document-level horizontal overflow, one h1,
English document language, and no axe violations tagged `wcag2a` or `wcag21a`.
Separate checks cover the mobile menu's keyboard/Escape behavior and navigation,
single-column listings at 360 px, details navigation, the skip link, and 404s.
These are automated Level A checks, not a complete manual accessibility audit.

## Manual browser acceptance

Playwright engines are useful regression coverage, but do not certify current and
previous branded browsers. Complete the following on actual browser releases:

| Browser | Current major               | Previous major              |
| ------- | --------------------------- | --------------------------- |
| Chrome  | Pending manual verification | Pending manual verification |
| Firefox | Pending manual verification | Pending manual verification |
| Edge    | Pending manual verification | Pending manual verification |
| Safari  | Pending manual verification | Pending manual verification |

For each browser:

1. Visit home, marketplace, listing detail, orders preview, and example order.
2. Check 360 px and desktop layouts: no horizontal scrolling, readable copy,
   single-column listing cards on mobile, and a collapsed mobile menu.
3. Use only the keyboard: skip link, menu button, Escape, page links, and focus indicators.
4. Confirm all UI copy is English, price/budget labels show UAH, and sample content
   is identified. Contact and order actions must be disabled.
5. Check headings, landmarks, reading order, and menu state with a screen reader;
   test at 200% zoom and with reduced motion enabled.

The SRS is unchanged. Remaining TBDs and legal policy approval retain their status.
