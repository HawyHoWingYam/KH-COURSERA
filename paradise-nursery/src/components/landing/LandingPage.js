import React from 'react';
import { Link } from 'react-router-dom';
import Button from '../common/Button';
import styles from '../../styles/Landing.module.css';

const LandingPage = () => {
  return (
    <div className={styles.landingContainer}>
      <div className={styles.landingContent}>
        <h1 className={styles.title}>Paradise Nursery</h1>
        <p className={styles.description}>
          Welcome to Paradise Nursery, your one-stop destination for beautiful, healthy houseplants. 
          We carefully select and nurture each plant to bring life and freshness to your home or office. 
          Whether you're a seasoned plant parent or just starting your green journey, 
          we have the perfect plant companions waiting for you.
        </p>
        <Link to="/products">
          <Button variant="primary" size="large">Get Started</Button>
        </Link>
      </div>
    </div>
  );
};

export default LandingPage;