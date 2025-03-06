// src/components/common/Button.js
import React from 'react';

const Button = ({ 
  children, 
  onClick, 
  disabled = false, 
  variant = 'primary', 
  size = 'medium',
  fullWidth = false,
  type = 'button'
}) => {
  const buttonClasses = [
    'button',
    variant === 'primary' ? 'buttonPrimary' : 'buttonSecondary',
    size === 'small' ? 'buttonSmall' : size === 'large' ? 'buttonLarge' : 'buttonMedium',
    fullWidth ? 'buttonFullWidth' : ''
  ].join(' ').trim();

  return (
    <button
      type={type}
      className={buttonClasses}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
};

export default Button;