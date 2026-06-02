// Relative URL — Nginx proxies /api/ to the backend container internally.
// This works on both localhost (dev) and the EC2 server (production).
const API_URL = "/api/customers";

document.getElementById("customerForm").addEventListener("submit", async (e) => {
  e.preventDefault();

  const customerId   = document.getElementById("customerId").value.trim();
  const customerName = document.getElementById("customerName").value.trim();
  const gender       = document.getElementById("gender").value;
  const age          = document.getElementById("age").value;
  const someNumber   = document.getElementById("someNumber").value;

  if (!customerId || !customerName || !gender || age === "" || someNumber === "") {
    showMessage("All fields are required.", "error");
    return;
  }

  // Business logic: multiply some_number by 2 before sending
  const processedSomeNumber = parseInt(someNumber, 10) * 2;

  const payload = {
    customer_id:   customerId,
    customer_name: customerName,
    gender:        gender,
    age:           parseInt(age, 10),
    some_number:   processedSomeNumber,
  };

  try {
    const response = await fetch(API_URL, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(payload),
    });

    const result = await response.json();

    if (response.ok && result.status === "success") {
      showMessage(result.message, "success");
      document.getElementById("customerForm").reset();
    } else {
      showMessage(result.message || "Something went wrong.", "error");
    }
  } catch (err) {
    showMessage("Unable to reach the server. Please try again.", "error");
  }
});

function showMessage(text, type) {
  const msg = document.getElementById("message");
  msg.textContent = text;
  msg.className = type;
  msg.style.display = "block";
  setTimeout(() => { msg.style.display = "none"; }, 4000);
}
