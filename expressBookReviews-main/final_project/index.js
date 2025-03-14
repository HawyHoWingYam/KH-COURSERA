const express = require('express');
const jwt = require('jsonwebtoken');
const session = require('express-session')
const customer_routes = require('./router/auth_users.js').authenticated;
const genl_routes = require('./router/general.js').general;

const app = express();

app.use(express.json());

app.use("/customer", session({ secret: "bookshop-secret-key", resave: true, saveUninitialized: true }))

app.use("/customer/auth/*", function auth(req, res, next) {
  // Check if session exists and is authenticated
  if (req.session && req.session.authenticated) {
    return next();
  }

  // No valid session, check for JWT token in authorization header
  const authHeader = req.headers.authorization;

  if (!authHeader) {
    return res.status(401).json({ message: "Error: Authentication token is missing" });
  }

  // Extract the token from the Authorization header (Bearer token)
  const token = authHeader.split(' ')[1];

  if (!token) {
    return res.status(401).json({ message: "Error: Authentication token is missing" });
  }

  // Verify the JWT token
  jwt.verify(token, "bookshop-secret-key", (err, user) => {
    if (err) {
      return res.status(403).json({ message: "Error: Authentication token is invalid or expired" });
    }

    // Store user data in the request for use in route handlers
    req.user = user;
    req.session.authenticated = true;
    next();
  });
});

const PORT = 3000;

app.use("/customer", customer_routes);
app.use("/", genl_routes);

app.listen(PORT, () => console.log("Server is running"));
