import React from 'react';
import styled, { keyframes } from 'styled-components';

const bounce = keyframes`
  0%, 80%, 100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
`;

const LoadingContainer = styled.div`
  display: inline-flex;
  gap: 0.25rem;
  padding: 0.5rem 1rem;
`;

const Dot = styled.div<{ delay: number }>`
  width: 8px;
  height: 8px;
  background-color: #8b4513;
  border-radius: 50%;
  animation: ${bounce} 1.4s infinite ease-in-out both;
  animation-delay: ${props => props.delay}s;
`;

const LoadingDots: React.FC = () => {
  return (
    <LoadingContainer>
      <Dot delay={-0.32} />
      <Dot delay={-0.16} />
      <Dot delay={0} />
    </LoadingContainer>
  );
};

export default LoadingDots;