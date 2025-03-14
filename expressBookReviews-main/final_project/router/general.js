const express = require('express');
const axios = require('axios');
let books = require("./booksdb.js");
let users = require("./auth_users.js").users;
const bookService = require('../services/bookService');
const public_users = express.Router();

// Update the registration route to include the following change
public_users.post("/register", (req, res) => {
  const { username, password } = req.body;

  if (!username || !password) {
    return res.status(400).json({ message: "Username and password are required" });
  }

  // Check if user already exists
  const userExists = users.some(user => user.username === username);
  if (userExists) {
    return res.status(409).json({ message: "Username already exists" });
  }

  // Add user to users array
  const newUser = { username, password };
  users.push(newUser);

  // Save users to JSON file
  const saveUsers = require("./auth_users.js").saveUsers;
  const saved = saveUsers();

  if (!saved) {
    return res.status(500).json({ message: "Error saving user data" });
  }

  return res.status(201).json({ message: "Registration successful" });
});

// Get the book list available in the shop (Original synchronous version)
public_users.get('/', function (req, res) {
  try {
    res.setHeader('Content-Type', 'application/json');
    res.status(200).send(JSON.stringify(books, null, 2));
  } catch (error) {
    return res.status(500).json({ message: error.message });
  }
});

// Get the book list using Promise callbacks
public_users.get('/promise', function (req, res) {
  bookService.getAllBooks()
    .then(books => {
      res.setHeader('Content-Type', 'application/json');
      res.status(200).send(JSON.stringify(books, null, 2));
    })
    .catch(error => {
      console.error("Error fetching books with promises:", error);
      res.status(500).json({ message: error.message });
    });
});

// Get the book list using async-await with Axios
public_users.get('/async', async function (req, res) {
  try {
    const response = await bookService.getAllBooksAxios();
    res.setHeader('Content-Type', 'application/json');
    res.status(200).send(JSON.stringify(response.data, null, 2));
  } catch (error) {
    console.error("Error fetching books with async-await:", error);
    res.status(500).json({ message: error.message });
  }
});

// Get book details based on ISBN
public_users.get('/isbn/:isbn', function (req, res) {
  try {
    const book = books[req.params.isbn];
    if (!book) {
      return res.status(404).json({ message: "Book not found" });
    }
    res.status(200).json(book);
  } catch (error) {
    return res.status(500).json({ message: error.message });
  }
});

// Get book details based on ISBN using Promise
public_users.get('/isbn/:isbn/promise', function (req, res) {
  const isbn = req.params.isbn;

  bookService.getBookByIsbn(isbn)
    .then(book => {
      if (!book) {
        return res.status(404).json({ message: "Book not found" });
      }
      res.status(200).json(book);
    })
    .catch(error => {
      console.error(`Error fetching book ${isbn} with promises:`, error);
      res.status(500).json({ message: error.message });
    });
});

// Get book details based on ISBN using async-await
public_users.get('/isbn/:isbn/async', async function (req, res) {
  try {
    const isbn = req.params.isbn;
    const book = await bookService.getBookByIsbn(isbn);

    if (!book) {
      return res.status(404).json({ message: "Book not found" });
    }

    res.status(200).json(book);
  } catch (error) {
    console.error(`Error fetching book with async-await:`, error);
    res.status(500).json({ message: error.message });
  }
});

// Get book details based on author
public_users.get('/author/:author', function (req, res) {
  try {
    const authorName = req.params.author;
    const matchingBooks = {};

    for (const [id, book] of Object.entries(books)) {
      if (book.author.includes(authorName)) {
        matchingBooks[id] = book;
      }
    }

    if (Object.keys(matchingBooks).length === 0) {
      return res.status(404).json({ message: `No books found by author: ${authorName}` });
    }

    res.status(200).json(matchingBooks);
  } catch (error) {
    return res.status(500).json({ message: error.message });
  }
});


// Get book details based on author using Promise
public_users.get('/author/:author/promise', function (req, res) {
  const authorName = req.params.author;

  bookService.getBooksByAuthor(authorName)
    .then(matchingBooks => {
      if (Object.keys(matchingBooks).length === 0) {
        return res.status(404).json({ message: `No books found by author: ${authorName}` });
      }
      res.status(200).json(matchingBooks);
    })
    .catch(error => {
      console.error(`Error fetching books by author with promises:`, error);
      res.status(500).json({ message: error.message });
    });
});

// Get book details based on author using async-await
public_users.get('/author/:author/async', async function (req, res) {
  try {
    const authorName = req.params.author;
    const matchingBooks = await bookService.getBooksByAuthor(authorName);

    if (Object.keys(matchingBooks).length === 0) {
      return res.status(404).json({ message: `No books found by author: ${authorName}` });
    }

    res.status(200).json(matchingBooks);
  } catch (error) {
    console.error(`Error fetching books by author with async-await:`, error);
    res.status(500).json({ message: error.message });
  }
});

// Get all books based on title
public_users.get('/title/:title', function (req, res) {
  try {
    const titleName = req.params.title;
    const matchingBooks = {};

    for (const [id, book] of Object.entries(books)) {
      if (book.title.includes(titleName)) {
        matchingBooks[id] = book;
      }
    }

    if (Object.keys(matchingBooks).length === 0) {
      return res.status(404).json({ message: `No books found by title: ${titleName}` });
    }

    res.status(200).json(matchingBooks);
  } catch (error) {
    return res.status(500).json({ message: error.message });
  }
});

// Get all books based on title using Promise
public_users.get('/title/:title/promise', function (req, res) {
  const titleName = req.params.title;

  bookService.getBooksByTitle(titleName)
    .then(matchingBooks => {
      if (Object.keys(matchingBooks).length === 0) {
        return res.status(404).json({ message: `No books found by title: ${titleName}` });
      }
      res.status(200).json(matchingBooks);
    })
    .catch(error => {
      console.error(`Error fetching books by title with promises:`, error);
      res.status(500).json({ message: error.message });
    });
});

// Get all books based on title using async-await
public_users.get('/title/:title/async', async function (req, res) {
  try {
    const titleName = req.params.title;
    const matchingBooks = await bookService.getBooksByTitle(titleName);

    if (Object.keys(matchingBooks).length === 0) {
      return res.status(404).json({ message: `No books found by title: ${titleName}` });
    }

    res.status(200).json(matchingBooks);
  } catch (error) {
    console.error(`Error fetching books by title with async-await:`, error);
    res.status(500).json({ message: error.message });
  }
});

// Get book review
public_users.get('/review/:isbn', function (req, res) {
  try {
    const book = books[req.params.isbn];
    if (!book) {
      return res.status(404).json({ message: "Book not found" });
    }
    res.status(200).json(book.reviews || {});
  } catch (error) {
    return res.status(500).json({ message: error.message });
  }
});

// Get book review using Promise
public_users.get('/review/:isbn/promise', function (req, res) {
  const isbn = req.params.isbn;

  bookService.getBookReviews(isbn)
    .then(reviews => {
      res.status(200).json(reviews);
    })
    .catch(error => {
      if (error.message.includes('not found')) {
        return res.status(404).json({ message: "Book not found" });
      }
      console.error(`Error fetching reviews with promises:`, error);
      res.status(500).json({ message: error.message });
    });
});

// Get book review using async-await
public_users.get('/review/:isbn/async', async function (req, res) {
  try {
    const isbn = req.params.isbn;
    const reviews = await bookService.getBookReviews(isbn);
    res.status(200).json(reviews);
  } catch (error) {
    if (error.message.includes('not found')) {
      return res.status(404).json({ message: "Book not found" });
    }
    console.error(`Error fetching reviews with async-await:`, error);
    res.status(500).json({ message: error.message });
  }
});

module.exports.general = public_users;