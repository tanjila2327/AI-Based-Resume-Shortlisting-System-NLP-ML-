const express = require("express");
const mysql = require("mysql2");
const bodyParser = require("body-parser");
const cors = require("cors");

const app = express();
app.use(cors());
app.use(bodyParser.json());

// ✅ Connect MySQL
const db = mysql.createConnection({
  host: "localhost",
  user: "root",      // your MySQL username
  password: "tanzila@123",      // your MySQL password
  database: "resume_db" // create this database in MySQL
});

db.connect(err => {
  if (err) throw err;
  console.log("✅ MySQL Connected...");
});

// ✅ Signup Route
app.post("/signup", (req, res) => {
  const { name, email, password } = req.body;
  const role = "recruiter"; // fixed role
  db.query("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)", 
    [name, email, password, role],
    (err, result) => {
      if (err) return res.status(500).send({ message: "Error: " + err });
      res.send({ message: "✅ User registered successfully!" });
    }
  );
});

// ✅ Login Route
app.post("/login", (req, res) => {
  const { email, password } = req.body;
  db.query("SELECT * FROM users WHERE email=? AND password=? AND role='recruiter'", 
    [email, password], 
    (err, results) => {
      if (err) return res.status(500).send({ message: "Error: " + err });
      if (results.length === 0) return res.status(401).send({ message: "❌ Invalid credentials" });
      res.send({ message: "✅ Login successful", user: results[0] });
    }
  );
});

app.listen(5000, () => console.log("🚀 Server running on http://localhost:5000"));
