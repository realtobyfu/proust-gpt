import React, { useState } from 'react';
import styled from 'styled-components';
import { theme } from '../styles/theme';

const MapContainer = styled.div`
  width: 100%;
  height: 600px;
  background: linear-gradient(to bottom, #f7f4f0, #ebe7e0);
  border-radius: 20px;
  padding: 2rem;
  overflow: auto;
  position: relative;
  box-shadow: inset 0 2px 10px rgba(0, 0, 0, 0.05);
`;

const VolumeTrack = styled.div`
  display: flex;
  gap: 2rem;
  padding: 2rem 0;
  min-width: max-content;
`;

const VolumeNode = styled.div<{ isActive?: boolean; isCompleted?: boolean }>`
  position: relative;
  cursor: pointer;
  transition: all ${theme.transitions.default};
  
  &:hover {
    transform: scale(1.05);
  }
`;

const VolumeCircle = styled.div<{ isActive?: boolean; isCompleted?: boolean }>`
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: ${props => 
    props.isCompleted ? theme.colors.primary : 
    props.isActive ? '#e8b04b' : 
    '#fff'};
  border: 3px solid ${props => 
    props.isActive ? theme.colors.primary : 
    props.isCompleted ? theme.colors.primary : 
    '#ddd'};
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  transition: all ${theme.transitions.default};
  
  &:hover {
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
  }
`;

const VolumeNumber = styled.div`
  font-size: 2rem;
  font-weight: bold;
  color: ${props => props.isCompleted ? '#fff' : theme.colors.text};
`;

const VolumeTitle = styled.div`
  font-size: 0.85rem;
  text-align: center;
  margin-top: 0.5rem;
  color: ${props => props.isCompleted ? '#fff' : theme.colors.textLight};
  max-width: 100px;
`;

const ConnectionLine = styled.div<{ progress?: number }>`
  position: absolute;
  top: 50%;
  left: 120px;
  width: calc(100% + 2rem);
  height: 3px;
  background: #ddd;
  transform: translateY(-50%);
  
  &::after {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    height: 100%;
    width: ${props => props.progress || 0}%;
    background: ${theme.colors.primary};
    transition: width ${theme.transitions.slow};
  }
`;

const ThemeMarker = styled.div<{ top: number; left: number; color: string }>`
  position: absolute;
  top: ${props => props.top}px;
  left: ${props => props.left}px;
  background: ${props => props.color};
  color: white;
  padding: 0.5rem 1rem;
  border-radius: 20px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all ${theme.transitions.default};
  z-index: 2;
  
  &:hover {
    transform: scale(1.1);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  }
`;

const ProgressInfo = styled.div`
  position: absolute;
  top: 1rem;
  right: 1rem;
  background: rgba(255, 255, 255, 0.9);
  padding: 1rem 1.5rem;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
`;

const ProgressStat = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
  
  &:last-child {
    margin-bottom: 0;
  }
`;

const StatLabel = styled.span`
  font-size: 0.9rem;
  color: ${theme.colors.textLight};
  margin-right: 1rem;
`;

const StatValue = styled.span`
  font-weight: bold;
  color: ${theme.colors.text};
`;

const Tooltip = styled.div<{ x: number; y: number; visible: boolean }>`
  position: absolute;
  top: ${props => props.y}px;
  left: ${props => props.x}px;
  background: rgba(0, 0, 0, 0.9);
  color: white;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  font-size: 0.9rem;
  opacity: ${props => props.visible ? 1 : 0};
  pointer-events: none;
  transition: opacity ${theme.transitions.default};
  z-index: 10;
  transform: translate(-50%, -120%);
  white-space: nowrap;
`;

interface Volume {
  id: number;
  title: string;
  progress: number;
  themes: { name: string; position: { top: number; left: number }; color: string }[];
}

interface JourneyMapProps {
  currentVolume?: number;
  onVolumeClick?: (volumeId: number) => void;
}

const JourneyMap: React.FC<JourneyMapProps> = ({ currentVolume = 1, onVolumeClick }) => {
  const [hoveredTheme, setHoveredTheme] = useState<string | null>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  const volumes: Volume[] = [
    { 
      id: 1, 
      title: "Swann's Way", 
      progress: 100,
      themes: [
        { name: "Involuntary Memory", position: { top: 20, left: 60 }, color: "#7a9cc6" },
        { name: "First Love", position: { top: 80, left: 40 }, color: "#d68a59" }
      ]
    },
    { 
      id: 2, 
      title: "Within a Budding Grove", 
      progress: 65,
      themes: [
        { name: "Adolescence", position: { top: 30, left: 70 }, color: "#87a96b" }
      ]
    },
    { 
      id: 3, 
      title: "The Guermantes Way", 
      progress: 30,
      themes: [
        { name: "Society", position: { top: 50, left: 50 }, color: "#9b7aa1" }
      ]
    },
    { 
      id: 4, 
      title: "Sodom and Gomorrah", 
      progress: 0,
      themes: []
    },
    { 
      id: 5, 
      title: "The Captive", 
      progress: 0,
      themes: []
    },
    { 
      id: 6, 
      title: "The Fugitive", 
      progress: 0,
      themes: []
    },
    { 
      id: 7, 
      title: "Time Regained", 
      progress: 0,
      themes: []
    }
  ];

  const totalProgress = volumes.reduce((acc, vol) => acc + vol.progress, 0) / volumes.length;

  const handleMouseMove = (e: React.MouseEvent) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setMousePos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

  return (
    <MapContainer onMouseMove={handleMouseMove}>
      <VolumeTrack>
        {volumes.map((volume, index) => (
          <VolumeNode 
            key={volume.id}
            isActive={volume.id === currentVolume}
            isCompleted={volume.progress === 100}
            onClick={() => onVolumeClick?.(volume.id)}
          >
            <VolumeCircle 
              isActive={volume.id === currentVolume}
              isCompleted={volume.progress === 100}
            >
              <VolumeNumber isCompleted={volume.progress === 100}>
                {volume.id}
              </VolumeNumber>
              <VolumeTitle isCompleted={volume.progress === 100}>
                {volume.title}
              </VolumeTitle>
            </VolumeCircle>
            
            {index < volumes.length - 1 && (
              <ConnectionLine progress={volume.progress} />
            )}
            
            {volume.themes.map(theme => (
              <ThemeMarker
                key={theme.name}
                top={theme.position.top}
                left={theme.position.left}
                color={theme.color}
                onMouseEnter={() => setHoveredTheme(theme.name)}
                onMouseLeave={() => setHoveredTheme(null)}
              >
                {theme.name}
              </ThemeMarker>
            ))}
          </VolumeNode>
        ))}
      </VolumeTrack>
      
      <ProgressInfo>
        <ProgressStat>
          <StatLabel>Overall Progress</StatLabel>
          <StatValue>{Math.round(totalProgress)}%</StatValue>
        </ProgressStat>
        <ProgressStat>
          <StatLabel>Current Volume</StatLabel>
          <StatValue>{currentVolume}</StatValue>
        </ProgressStat>
        <ProgressStat>
          <StatLabel>Pages Read</StatLabel>
          <StatValue>1,247</StatValue>
        </ProgressStat>
        <ProgressStat>
          <StatLabel>Time Invested</StatLabel>
          <StatValue>42h 15m</StatValue>
        </ProgressStat>
      </ProgressInfo>
      
      <Tooltip 
        x={mousePos.x} 
        y={mousePos.y} 
        visible={!!hoveredTheme}
      >
        {hoveredTheme}
      </Tooltip>
    </MapContainer>
  );
};

export default JourneyMap;