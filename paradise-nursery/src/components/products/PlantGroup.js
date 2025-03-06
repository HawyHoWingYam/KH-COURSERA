// src/components/products/PlantGroup.js
import React from 'react';
import PlantCard from './PlantCard';
import styles from '../../styles/Products.module.css';

const PlantGroup = ({ category, plants }) => {
  return (
    <section className={styles.plantGroup}>
      <h2 className={styles.categoryTitle}>{category}</h2>
      <div className={styles.plantsGrid}>
        {plants.map(plant => (
          <PlantCard key={plant.id} plant={plant} />
        ))}
      </div>
    </section>
  );
};

export default PlantGroup;