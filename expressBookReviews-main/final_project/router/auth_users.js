const express = require('express');
const jwt = require('jsonwebtoken');
const fs = require('fs');
const path = require('path');
let books = require("./booksdb.js");
const regd_users = express.Router();

// Load users from JSON file
const usersFilePath = path.join(__dirname, '../data/users.json');
let users = [];

try {
  const data = fs.readFileSync(usersFilePath, 'utf8');
  if (data) {
    users = JSON.parse(data);
  }
} catch (err) {
  // If file doesn't exist or is empty, initialize with empty array
  console.log('Initializing users with empty array');
}


// JWT configuration
const JWT_SECRET = 'bookshop-secret-key';
const JWT_EXPIRY = '24h';


// Save users to JSON file
const saveUsers = () => {
  try {
    fs.writeFileSync(usersFilePath, JSON.stringify(users, null, 2));
    return true;
  } catch (err) {
    console.error('Error saving users:', err);
    return false;
  }
};




const isValid = (username) => { // returns boolean
  // Check if username exists and is not empty
  return username && typeof username === 'string' && username.trim().length > 0;
};

const authenticatedUser = (username, password) => { // returns boolean
  // Find the user with matching username and password
  const user = users.find(u => u.username === username && u.password === password);
  return user !== undefined;
};


// Only registered users can login
regd_users.post("/login", (req, res) => {
  const { username, password } = req.body;

  // Validate input
  if (!username || !password) {
    return res.status(400).json({ message: "Username and password are required" });
  }

  // Check if user exists and password matches
  if (!authenticatedUser(username, password)) {
    return res.status(401).json({ message: "Invalid username or password" });
  }

  // Generate JWT token
  const token = jwt.sign({ username }, JWT_SECRET, { expiresIn: JWT_EXPIRY });

  // Return token to client
  return res.status(200).json({
    message: "Login successful",
    token: token
  });
});

// Middleware to verify JWT token
const verifyToken = (req, res, next) => {
  const token = req.headers.authorization?.split(' ')[1]; // Bearer TOKEN format


  if (!token) {
    return res.status(401).json({ message: "No token provided" });
  }

  try {
    const decoded = jwt.verify(token, JWT_SECRET);

    req.user = decoded;
    next();
  } catch (error) {
    return res.status(401).json({ message: "Invalid or expired token" });
  }
};



// Add or modify a book review - requires authentication
regd_users.put("/auth/review/:isbn", verifyToken, (req, res) => {
  try {
    const isbn = req.params.isbn;
    const review = req.query.review; // Get review from query parameter
    const username = req.user.username; // Username from JWT token

    // Validate inputs
    if (!isbn) {
      return res.status(400).json({ message: "ISBN is required" });
    }

    if (!review || review.trim() === '') {
      return res.status(400).json({ message: "Review text is required" });
    }

    // Check if book exists
    if (!books[isbn]) {
      return res.status(404).json({ message: "Book not found" });
    }

    // Initialize reviews object if it doesn't exist
    if (!books[isbn].reviews) {
      books[isbn].reviews = {};
    }

    // Check if this is an update to an existing review
    const isUpdate = books[isbn].reviews.hasOwnProperty(username);
    const previousReview = isUpdate ? books[isbn].reviews[username] : null;

    // Add or update the review
    books[isbn].reviews[username] = review;

    return res.status(200).json({
      message: isUpdate ? "Review updated successfully" : "Review added successfully",
      book: {
        isbn: isbn,
        title: books[isbn].title,
        author: books[isbn].author
      },
      review: {
        username: username,
        text: review,
        previousReview: isUpdate ? previousReview : undefined
      }
    });
  } catch (error) {
    console.error("Error processing review:", error);
    return res.status(500).json({
      message: "An error occurred while processing your review",
      error: error.message
    });
  }
});

// Get all reviews by the authenticated user
regd_users.get("/auth/reviews", verifyToken, (req, res) => {
  try {
    const username = req.user.username;
    const userReviews = {};

    // Find all reviews by this user across all books
    for (const [isbn, book] of Object.entries(books)) {
      if (book.reviews && book.reviews[username]) {
        userReviews[isbn] = {
          title: book.title,
          author: book.author,
          review: book.reviews[username]
        };
      }
    }

    if (Object.keys(userReviews).length === 0) {
      return res.status(404).json({ message: "You haven't submitted any reviews yet" });
    }

    return res.status(200).json({
      username: username,
      reviewCount: Object.keys(userReviews).length,
      reviews: userReviews
    });

  } catch (error) {
    console.error("Error retrieving user reviews:", error);
    return res.status(500).json({ message: "Error retrieving reviews", error: error.message });
  }
});


regd_users.delete("/auth/review/:isbn", verifyToken, (req, res) => {
  try {
    const isbn = req.params.isbn;
    const username = req.user.username; // Username from JWT token
    
    console.log(`Attempting to delete review for ISBN ${isbn} by user ${username}`);
    
    // Validate inputs
    if (!isbn) {
      console.log('Error: Missing ISBN parameter');
      return res.status(400).json({ message: "ISBN is required" });
    }
    
    // Check if book exists
    if (!books[isbn]) {
      console.log(`Error: Book with ISBN ${isbn} not found`);
      return res.status(404).json({ message: "Book not found" });
    }
    
    // Check if the book has any reviews
    if (!books[isbn].reviews) {
      console.log(`Error: No reviews exist for book with ISBN ${isbn}`);
      return res.status(404).json({ message: "No reviews found for this book" });
    }
    
    // Check if the user has a review for this book
    if (!books[isbn].reviews.hasOwnProperty(username)) {
      console.log(`Error: User ${username} has no review for book with ISBN ${isbn}`);
      return res.status(404).json({ message: "You have not reviewed this book" });
    }
    
    // Store the review content before deletion for the response
    const deletedReview = books[isbn].reviews[username];
    
    // Delete the user's review
    delete books[isbn].reviews[username];
    console.log(`Success: Review by ${username} for ISBN ${isbn} was deleted`);
    
    // If this was the last review, clean up the reviews object
    if (Object.keys(books[isbn].reviews).length === 0) {
      console.log(`Removing empty reviews object for ISBN ${isbn}`);
      delete books[isbn].reviews;
    }
    
    return res.status(200).json({
      message: "Review deleted successfully",
      book: {
        isbn: isbn,
        title: books[isbn].title,
        author: books[isbn].author
      },
      deletedReview: {
        username: username,
        text: deletedReview
      }
    });
  } catch (error) {
    console.error("Error deleting review:", error);
    console.error(`- Error name: ${error.name}`);
    console.error(`- Error message: ${error.message}`);
    console.error(`- Stack trace: ${error.stack}`);
    return res.status(500).json({
      message: "An error occurred while deleting your review",
      error: error.message
    });
  }
});

module.exports.authenticated = regd_users;
module.exports.isValid = isValid;
module.exports.users = users;
module.exports.saveUsers = saveUsers;
