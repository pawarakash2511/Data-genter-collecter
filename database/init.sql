CREATE DATABASE IF NOT EXISTS customerdb;
USE customerdb;

CREATE TABLE IF NOT EXISTS customers (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  customer_id   VARCHAR(100)  NOT NULL,
  customer_name VARCHAR(255)  NOT NULL,
  gender        VARCHAR(20)   NOT NULL,
  age           INT           NOT NULL,
  some_number   INT           NOT NULL,
  submitted_at  DATETIME      NOT NULL
);
