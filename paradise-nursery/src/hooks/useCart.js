import { useState, useContext } from 'react';
import { CartContext } from '../context/CartContext';

const useCart = () => {
    const { cartItems, setCartItems } = useContext(CartContext);
    
    const addToCart = (plant) => {
        const existingItem = cartItems.find(item => item.id === plant.id);
        if (existingItem) {
            setCartItems(cartItems.map(item => 
                item.id === plant.id 
                ? { ...item, quantity: item.quantity + 1 } 
                : item
            ));
        } else {
            setCartItems([...cartItems, { ...plant, quantity: 1 }]);
        }
    };

    const removeFromCart = (plantId) => {
        setCartItems(cartItems.filter(item => item.id !== plantId));
    };

    const increaseQuantity = (plantId) => {
        setCartItems(cartItems.map(item => 
            item.id === plantId 
            ? { ...item, quantity: item.quantity + 1 } 
            : item
        ));
    };

    const decreaseQuantity = (plantId) => {
        const existingItem = cartItems.find(item => item.id === plantId);
        if (existingItem.quantity === 1) {
            removeFromCart(plantId);
        } else {
            setCartItems(cartItems.map(item => 
                item.id === plantId 
                ? { ...item, quantity: item.quantity - 1 } 
                : item
            ));
        }
    };

    const getTotalItems = () => {
        return cartItems.reduce((total, item) => total + item.quantity, 0);
    };

    const getTotalCost = () => {
        return cartItems.reduce((total, item) => total + (item.price * item.quantity), 0).toFixed(2);
    };

    return {
        cartItems,
        addToCart,
        removeFromCart,
        increaseQuantity,
        decreaseQuantity,
        getTotalItems,
        getTotalCost
    };
};

export default useCart;