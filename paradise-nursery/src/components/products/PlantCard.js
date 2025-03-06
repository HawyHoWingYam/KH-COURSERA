// Enhanced PlantCard.js with image loading state
import React, { useState } from 'react';
import Button from '../common/Button';
import { useCart } from '../../context/CartContext';
import styles from '../../styles/Products.module.css';

const PlantCard = ({ plant }) => {
  const { addToCart, cartItems } = useCart();
  const [isAdded, setIsAdded] = useState(
    cartItems.some(item => item.id === plant.id)
  );
  const [imageLoaded, setImageLoaded] = useState(false);
  
  const handleAddToCart = () => {
    addToCart(plant);
    setIsAdded(true);
  };

  return (
    <div className={styles.plantCard}>
      <div className={imageLoaded ? '' : styles.imagePlaceholder}>
        <img 
          src={plant.image} 
          alt={plant.name} 
          className={styles.plantImage} 
          onLoad={() => setImageLoaded(true)}
          style={{ display: imageLoaded ? 'block' : 'none' }}
        />
      </div>
      <div className={styles.plantInfo}>
        <h3 className={styles.plantName}>{plant.name}</h3>
        <p className={styles.plantPrice}>${plant.price.toFixed(2)}</p>
        <p className={styles.plantDescription}>{plant.description}</p>
        <Button 
          onClick={handleAddToCart} 
          disabled={isAdded}
          variant="primary"
        >
          {isAdded ? 'Added to Cart' : 'Add to Cart'}
        </Button>
      </div>
    </div>
  );
};

export default PlantCard;