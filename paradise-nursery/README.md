# Paradise Nursery React Application

## Overview
Paradise Nursery is a React.js application designed to showcase and sell a variety of houseplants. The application consists of three main pages: a Landing Page, a Product Listing Page, and a Shopping Cart Page. Each page is designed to provide a seamless user experience while highlighting the beauty and benefits of houseplants.

## Project Structure
The project is organized into the following main directories:

- **public/**: Contains static files such as HTML, images, and icons.
- **src/**: Contains all the React components, context, hooks, and styles.

## Pages
1. **Landing Page**: 
   - Features a background image and a description of Paradise Nursery.
   - Includes a "Get Started" button that navigates to the Product Listing Page.

2. **Product Listing Page**: 
   - Displays a list of houseplants grouped by common features (e.g., "Air Purifying").
   - Each plant is represented as a card with an image, name, price, description, and an "Add to Cart" button.

3. **Shopping Cart Page**: 
   - Shows items added to the cart with options to adjust quantities or remove items.
   - Displays the total number of items and the total cost, along with a "Checkout" button.

## Components
- **Header**: A common header for the Product Listing and Shopping Cart Pages, including the company logo and shopping cart icon.
- **Button**: A reusable button component for various actions throughout the application.
- **PlantCard**: Displays individual plant details in a card format.

## Context and State Management
- **CartContext**: Manages the state of the shopping cart, allowing components to access and modify cart data.
- **useCart Hook**: A custom hook that provides functions for adding, removing, and updating items in the cart.

## Styles
- Global styles are defined in `global.css`, while specific styles for each component are organized in their respective module CSS files.

## Setup Instructions
1. Clone the repository:
   ```
   git clone <repository-url>
   ```
2. Navigate to the project directory:
   ```
   cd paradise-nursery
   ```
3. Install dependencies:
   ```
   npm install
   ```
4. Start the development server:
   ```
   npm start
   ```

## Usage
- Visit the Landing Page to learn about Paradise Nursery.
- Navigate to the Product Listing Page to browse available houseplants.
- Add plants to your cart and view them on the Shopping Cart Page.

## Contributing
Contributions are welcome! Please submit a pull request or open an issue for any suggestions or improvements.

## License
This project is licensed under the MIT License.