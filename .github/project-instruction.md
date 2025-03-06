
**I. Overall Application Structure:**

The application will consist of three pages:

* **Landing Page:** Introduction to the Paradise Nursery.
* **Product Listing Page:** Displays available houseplants.
* **Shopping Cart Page:** Shows items added to the cart and allows for adjustments.

**II. Detailed Page Requirements:**

* **A. Landing Page:**
    * Include a background image.
    * Display the company name ("Paradise Nursery").
    * Show a paragraph describing the company and engaging potential customers.
    * Provide a "Get Started" button that links to the Product Listing Page.

* **B. Product Listing Page:**
    * Display a header (see section D below).
    * Show at least six unique houseplants.
    * Group the plants by a common feature (e.g., "Air Purifying," "Aromatic"). Some plants may belong to multiple groups.
    * Display each plant as a card with:
        * A thumbnail image.
        * The plant's name.
        * The plant's price.
        * A brief description.
        * An "Add to Cart" button.
            * When the "Add to Cart" button is clicked:
                * Disable the button and change its label to "Added to Cart".
                * Increment the cart icon's counter by one (see section D below).

* **C. Shopping Cart Page:**
    * Display the same header as the Product Listing Page (see section D below).
    * Organize the shopping cart items using cards. Each card should represent one type of plant added from the product listing page and include:
        * A thumbnail image.
        * A delete option (e.g., a button or icon).
        * The unit price of the plant.
        * An "Increase" button to increment the quantity of that plant type.
        * A "Decrease" button to decrement the quantity of that plant type.
        * The subtotal for that plant type (quantity \* unit price).
    * Prominently display:
        * The total number of plants in the cart.
        * The sum of the total costs of all items.
        * A "Checkout" button (for now, it can display a "Coming Soon" message or similar).
    * Handle user events such as:
        * When the number of items of a specific plant type in the cart decreases to zero:
            * Re-enable the corresponding "Add to Cart" button on the Product Listing Page so the user can add it again.
        * When using increase/decrease buttons:
            * Adjust the number of items shown on the cart icon in the header.

* **D. Header (Product Listing and Shopping Cart Pages):**
    * The header should be the same on both the Product Listing Page and the Shopping Cart Page.
    * Include:
        * The company name and logo (which should navigate back to the Landing Page when clicked).
        * A tagline.
        * A shopping cart icon.
        * A counter displayed on the shopping cart icon showing the current number of items in the cart.

**III. Development Guidance:**

* I plan to use React.js for this project.
* Please provide guidance on best practices for structuring my components, managing state, and handling events.
* Offer suggestions for styling (e.g., CSS, CSS-in-JS libraries).
* Provide code examples where appropriate.
* Assume I have a basic understanding of HTML, CSS, and JavaScript.
