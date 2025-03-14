/**
 * Book Service
 * 
 * This service simulates API calls to retrieve book data.
 * In a real application, this would make actual HTTP requests to a backend service.
 */
const axios = require('axios');
const booksData = require('../router/booksdb.js');

// Simulate an API endpoint URL (would be a real URL in production)
const API_BASE_URL = 'https://api.bookreviews.example/books';

/**
 * Simulates fetching all books from an API
 * @returns {Promise<Object>} Promise resolving to the books data
 */
const getAllBooks = () => {
  // Simulate network delay and potential failures
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      // Simulate occasional failures (10% chance)
      if (Math.random() < 0.1) {
        reject(new Error('Failed to fetch books. Network error.'));
      } else {
        resolve(booksData);
      }
    }, 300); // Simulate 300ms network delay
  });
};

/**
 * Simulates fetching a book by ISBN from an API
 * @param {string} isbn - The ISBN of the book to fetch
 * @returns {Promise<Object|null>} Promise resolving to the book data or null if not found
 */
const getBookByIsbn = (isbn) => {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (Math.random() < 0.05) {
        reject(new Error(`Failed to fetch book with ISBN ${isbn}. Network error.`));
      } else {
        const book = booksData[isbn] || null;
        resolve(book);
      }
    }, 200);
  });
};

/**
 * Simulates fetching books by author from an API
 * @param {string} author - The author name to search for
 * @returns {Promise<Object>} Promise resolving to an object of books by the author
 */
const getBooksByAuthor = (author) => {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (Math.random() < 0.05) {
        reject(new Error(`Failed to fetch books by author ${author}. Network error.`));
      } else {
        const matchingBooks = {};
        for (const [isbn, book] of Object.entries(booksData)) {
          if (book.author.includes(author)) {
            matchingBooks[isbn] = book;
          }
        }
        resolve(matchingBooks);
      }
    }, 250);
  });
};

/**
 * Simulates fetching books by title from an API
 * @param {string} title - The title to search for
 * @returns {Promise<Object>} Promise resolving to an object of books matching the title
 */
const getBooksByTitle = (title) => {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (Math.random() < 0.05) {
        reject(new Error(`Failed to fetch books with title ${title}. Network error.`));
      } else {
        const matchingBooks = {};
        for (const [isbn, book] of Object.entries(booksData)) {
          if (book.title.includes(title)) {
            matchingBooks[isbn] = book;
          }
        }
        resolve(matchingBooks);
      }
    }, 250);
  });
};

/**
 * Simulates fetching reviews for a book from an API
 * @param {string} isbn - The ISBN of the book to fetch reviews for
 * @returns {Promise<Object>} Promise resolving to the reviews for the book
 */
const getBookReviews = (isbn) => {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (Math.random() < 0.05) {
        reject(new Error(`Failed to fetch reviews for book ${isbn}. Network error.`));
      } else {
        const book = booksData[isbn];
        if (!book) {
          reject(new Error(`Book with ISBN ${isbn} not found`));
        } else {
          resolve(book.reviews || {});
        }
      }
    }, 150);
  });
};

// For Axios example, this simulates what would be an actual API call
// In a real application, this would call an external API
const getAllBooksAxios = async () => {
  try {
    // In a real app, this would be an actual HTTP request
    // return await axios.get(API_BASE_URL);
    
    // Simulate the axios response structure
    return {
      data: booksData,
      status: 200,
      statusText: 'OK',
      headers: {
        'content-type': 'application/json'
      },
    };
  } catch (error) {
    throw error;
  }
};

module.exports = {
  getAllBooks,
  getBookByIsbn,
  getBooksByAuthor,
  getBooksByTitle,
  getBookReviews,
  getAllBooksAxios
};