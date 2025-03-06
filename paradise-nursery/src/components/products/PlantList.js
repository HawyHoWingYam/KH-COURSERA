// src/components/products/PlantList.js
import React from 'react';
import PlantGroup from './PlantGroup';
import { getPlantsByCategory } from '../../data/plants';
import styles from '../../styles/Products.module.css';

const PlantList = () => {
  const plantCategories = getPlantsByCategory();
  
  return (
    <div className={styles.plantListContainer}>
      {Object.entries(plantCategories).map(([category, plants]) => (
        <PlantGroup key={category} category={category} plants={plants} />
      ))}
    </div>
  );
};

export default PlantList;