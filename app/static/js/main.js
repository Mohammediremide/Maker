function getCart() {
  try {
    return JSON.parse(localStorage.getItem("cart_items")) || [];
  } catch {
    return [];
  }
}

function saveCart(items) {
  localStorage.setItem("cart_items", JSON.stringify(items));
}

function resolveImageSrc(image) {
  if (!image) return "/static/images/products/sneakers.png";
  if (image.startsWith("http://") || image.startsWith("https://")) return image;
  return `/static/images/products/${image}`;
}

function formatPrice(value) {
  return `₦${value.toLocaleString()}`;
}

function updateCartCount() {
  const countEl = document.getElementById("cartCount");
  if (!countEl) return;
  const items = getCart();
  const count = items.reduce((sum, item) => sum + item.qty, 0);
  countEl.textContent = count;
}

function addToCart(item) {
  const items = getCart();
  const existing = items.find((i) => i.id === item.id);
  if (existing) {
    existing.qty += 1;
  } else {
    items.push({ ...item, qty: 1 });
  }
  saveCart(items);
  updateCartCount();
}

function renderCart() {
  const cartList = document.getElementById("cartList");
  const cartTable = document.getElementById("cartTable");
  const cartEmpty = document.getElementById("cartEmpty");
  const subtotalEl = document.getElementById("cartSubtotal");

  if (!cartList || !cartTable || !cartEmpty || !subtotalEl) return;

  const items = getCart();
  if (items.length === 0) {
    cartEmpty.style.display = "block";
    cartTable.style.display = "none";
    return;
  }

  cartEmpty.style.display = "none";
  cartTable.style.display = "block";

  cartList.innerHTML = "";
  let subtotal = 0;

  items.forEach((item, index) => {
    const row = document.createElement("div");
    row.className = "cart-row";

    const total = item.price * item.qty;
    subtotal += total;

    row.innerHTML = `
      <div class="cart-item">
        <img src="${resolveImageSrc(item.image)}" alt="${item.name}" />
        <div>
          <strong>${item.name}</strong>
          <p>${item.tag || ""}</p>
        </div>
      </div>
      <span>${formatPrice(item.price)}</span>
      <input type="number" min="1" value="${item.qty}" data-index="${index}" class="qty-input" />
      <span>${formatPrice(total)}</span>
      <button class="ghost-btn remove-btn" data-index="${index}">Remove</button>
    `;

    cartList.appendChild(row);
  });

  subtotalEl.textContent = formatPrice(subtotal);

  document.querySelectorAll(".qty-input").forEach((input) => {
    input.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.index, 10);
      const value = parseInt(e.target.value, 10);
      const items = getCart();
      if (value > 0) {
        items[idx].qty = value;
        saveCart(items);
        renderCart();
        updateCartCount();
      }
    });
  });

  document.querySelectorAll(".remove-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const idx = parseInt(e.target.dataset.index, 10);
      const items = getCart();
      items.splice(idx, 1);
      saveCart(items);
      renderCart();
      updateCartCount();
    });
  });
}

function renderCheckout() {
  const checkoutItems = document.getElementById("checkoutItems");
  const checkoutTotal = document.getElementById("checkoutTotal");
  const cartJson = document.getElementById("cartJson");

  if (!checkoutItems || !checkoutTotal || !cartJson) return;

  const items = getCart();
  let total = 0;
  checkoutItems.innerHTML = "";

  items.forEach((item) => {
    const line = document.createElement("div");
    line.className = "checkout-item";
    line.innerHTML = `<span>${item.name} x ${item.qty}</span><span>${formatPrice(item.price * item.qty)}</span>`;
    checkoutItems.appendChild(line);
    total += item.price * item.qty;
  });

  checkoutTotal.textContent = formatPrice(total);
  cartJson.value = JSON.stringify(items);
}

function wireAddToCart() {
  // Use event delegation on document to catch all clicks on .add-to-cart
  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".add-to-cart");
    if (!btn) return;

    // We don't need data-wired anymore with delegation
    const item = {
      id: parseInt(btn.dataset.id, 10),
      name: btn.dataset.name,
      price: parseInt(btn.dataset.price, 10),
      image: btn.dataset.image,
    };
    
    addToCart(item);
    
    // Provide feedback
    const originalText = btn.textContent;
    btn.textContent = "Added!";
    btn.classList.add("added"); 
    setTimeout(() => {
      btn.textContent = originalText;
      btn.classList.remove("added");
    }, 1200);
  });
}

document.addEventListener("DOMContentLoaded", () => {
    updateCartCount();
    wireAddToCart();
    renderCart();
    renderCheckout();
});
