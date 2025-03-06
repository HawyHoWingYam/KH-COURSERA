// src/components/cart/CartItem.js
import React from 'react';
import Button from '../common/Button';
import { useCart } from '../../context/CartContext';
import styles from '../../styles/Cart.module.css';

const CartItem = ({ item }) => {
  const { updateQuantity, removeFromCart } = useCart();
  const subtotal = (item.price * item.quantity).toFixed(2);

  const handleIncrease = () => {
    updateQuantity(item.id, item.quantity + 1);
  };

  const handleDecrease = () => {
    updateQuantity(item.id, item.quantity - 1);
  };

  return (
    <div className={styles.cartItem}>
      <img 
        src={item.image} 
        alt={item.name} 
        className={styles.cartItemImage} 
      />
      <div className={styles.cartItemInfo}>
        <h3 className={styles.cartItemName}>{item.name}</h3>
        <p className={styles.cartItemPrice}>${item.price.toFixed(2)} each</p>
      </div>
      <div className={styles.cartItemActions}>
        <div className={styles.quantityControl}>
          <Button 
            onClick={handleDecrease} 
            variant="secondary"
            size="small"
          >
            -
          </Button>
          <span className={styles.quantity}>{item.quantity}</span>
          <Button 
            onClick={handleIncrease} 
            variant="secondary"
            size="small"
          >
            +
          </Button>
        </div>
        <p className={styles.subtotal}>Subtotal: ${subtotal}</p>
        <Button 
          onClick={() => removeFromCart(item.id)} 
          variant="secondary"
          size="small"
        >
          Remove
        </Button>
      </div>
    </div>
  );
};

export default CartItem;