// src/components/products/ProductListingPage.js
import React from 'react';
import Header from '../common/Header';
import PlantList from './PlantList';
import styles from '../../styles/Products.module.css';

const ProductListingPage = () => {
  return (
    <div className={styles.productsContainer}>
      <Header />
      <main className={styles.productsMain}>
        <h1 className={styles.pageTitle}>Our Houseplants Collection</h1>
        <p className={styles.pageDescription}>
          Browse our selection of beautiful, easy-to-care-for houseplants that will brighten up any space.
        </p>
        <PlantList />
      </main>
    </div>
  );
};

export default ProductListingPage;