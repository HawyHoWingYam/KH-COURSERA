import plant1Image from '../assets/images/plants/plant1.jpg';
import plant2Image from '../assets/images/plants/plant2.jpg';
import plant3Image from '../assets/images/plants/plant3.jpg';
import plant4Image from '../assets/images/plants/plant4.jpg';
import plant5Image from '../assets/images/plants/plant5.jpg';
import plant6Image from '../assets/images/plants/plant6.jpg';

const plants = [
    {
      id: 1,
      name: "Snake Plant",
      price: 24.99,
      description: "Easy to care for and purifies air.",
      image: plant1Image,
      categories: ["Air Purifying", "Low Maintenance"]
    },
    {
      id: 2,
      name: "Pothos",
      price: 18.99,
      description: "Trailing vine that's perfect for beginners.",
      image: plant2Image,
      categories: ["Air Purifying", "Low Maintenance"]
    },
    {
      id: 3,
      name: "Peace Lily",
      price: 29.99,
      description: "Elegant white flowers and excellent air purifier.",
      image: plant3Image,
      categories: ["Air Purifying", "Flowering"]
    },
    {
      id: 4,
      name: "Lavender",
      price: 15.99,
      description: "Beautiful purple blooms with calming fragrance.",
      image: plant4Image,
      categories: ["Aromatic", "Flowering"]
    },
    {
      id: 5,
      name: "Spider Plant",
      price: 12.99,
      description: "Produces baby plants that can be propagated.",
      image: plant5Image,
      categories: ["Air Purifying", "Pet Friendly"]
    },
    {
      id: 6,
      name: "Mint",
      price: 8.99,
      description: "Fragrant herb perfect for cooking and cocktails.",
      image: plant6Image,
      categories: ["Aromatic", "Edible"]
    }
  ];
  
  // Group plants by category
  export const getPlantsByCategory = () => {
    const categories = {};
    
    plants.forEach(plant => {
      plant.categories.forEach(category => {
        if (!categories[category]) {
          categories[category] = [];
        }
        categories[category].push(plant);
      });
    });
    
    return categories;
  };
  
  export default plants;