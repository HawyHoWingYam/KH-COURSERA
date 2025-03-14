const express = require('express');
let books = require("./booksdb.js");
let isValid = require("./auth_users.js").isValid;
let users = require("./auth_users.js").users;
const public_users = express.Router();


public_users.post("/register", (req, res) => {
  const { username, password } = req.body;
  
  if (!username || !password) {
    return res.status(400).json({ message: "Username and password are required" });
  }
  
  if (users[username]) {
    return res.status(409).json({ message: "Username already exists" });
  }
  
  users[username] = { username, password };
  return res.status(201).json({ message: "Registration successful" });
});

// Get the book list available in the shop
public_users.get('/', function (req, res) {
  try {
    res.setHeader('Content-Type', 'application/json');
    res.status(200).send(JSON.stringify(books, null, 2));
  } catch (error) {
    return res.status(500).json({ message: error.message });
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

//  Get book review
public_users.get('/review/:isbn', function (req, res) {
  try {
    const book = books[req.params.isbn];
    if (!book) {
      return res.status(404).json({ message: "Book not found" });
    }
    res.status(200).json(book.reviews);
  } catch (error) {
    return res.status(500).json({ message: error.message });
  }
});

module.exports.general = public_users;
