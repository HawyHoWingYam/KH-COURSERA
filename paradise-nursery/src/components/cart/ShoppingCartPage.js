// src/components/cart/ShoppingCartPage.js
import React from 'react';
import Header from '../common/Header';
import CartItem from './CartItem';
import CartSummary from './CartSummary';
import { useCart } from '../../context/CartContext';
import styles from '../../styles/Cart.module.css';

const ShoppingCartPage = () => {
  const { cartItems, cartCount } = useCart();

  return (
    <div className={styles.cartContainer}>
      <Header />
      <main className={styles.cartMain}>
        <h1 className={styles.pageTitle}>Your Shopping Cart</h1>
        
        {cartCount === 0 ? (
          <div className={styles.emptyCart}>
            <p>Your cart is empty. Start adding some plants!</p>
          </div>
        ) : (
          <div className={styles.cartContent}>
            <div className={styles.cartItems}>
              {cartItems.map(item => (
                <CartItem key={item.id} item={item} />
              ))}
            </div>
            <CartSummary />
          </div>
        )}
      </main>
    </div>
  );
};

export default ShoppingCartPage;