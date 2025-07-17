import React from 'react';
import styled from 'styled-components';
import { theme } from '../styles/theme';

const TrackerContainer = styled.div`
  background: rgba(255, 255, 255, 0.95);
  border-radius: 16px;
  padding: 2rem;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
`;

const Title = styled.h3`
  font-family: ${theme.fonts.heading};
  font-size: 1.5rem;
  margin-bottom: 2rem;
  color: ${theme.colors.text};
`;

const StatsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.5rem;
  margin-bottom: 2rem;
`;

const StatCard = styled.div`
  text-align: center;
  padding: 1.5rem;
  background: rgba(247, 244, 240, 0.8);
  border-radius: 12px;
  border: 1px solid rgba(139, 69, 19, 0.1);
`;

const StatValue = styled.div`
  font-size: 2.5rem;
  font-weight: bold;
  color: ${theme.colors.primary};
  margin-bottom: 0.5rem;
`;

const StatLabel = styled.div`
  font-size: 0.9rem;
  color: ${theme.colors.textLight};
`;

const MilestoneSection = styled.div`
  margin-top: 2rem;
`;

const MilestoneTitle = styled.h4`
  font-family: ${theme.fonts.secondary};
  font-size: 1.2rem;
  margin-bottom: 1rem;
  color: ${theme.colors.text};
`;

const MilestoneList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 1rem;
`;

const Milestone = styled.div<{ achieved: boolean }>`
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  background: ${props => props.achieved ? 'rgba(139, 69, 19, 0.1)' : 'rgba(0, 0, 0, 0.03)'};
  border-radius: 8px;
  transition: all ${theme.transitions.default};
  
  ${props => props.achieved && `
    border: 1px solid ${theme.colors.primary};
  `}
`;

const MilestoneIcon = styled.div<{ achieved: boolean }>`
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: ${props => props.achieved ? theme.colors.primary : '#ddd'};
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.2rem;
`;

const MilestoneContent = styled.div`
  flex: 1;
`;

const MilestoneName = styled.div`
  font-weight: 500;
  color: ${theme.colors.text};
  margin-bottom: 0.25rem;
`;

const MilestoneDescription = styled.div`
  font-size: 0.85rem;
  color: ${theme.colors.textLight};
`;

const AchievementDate = styled.div`
  font-size: 0.85rem;
  color: ${theme.colors.textLight};
`;

const ReadingStreak = styled.div`
  margin-top: 2rem;
  padding: 1.5rem;
  background: linear-gradient(135deg, rgba(232, 176, 75, 0.1), rgba(139, 69, 19, 0.1));
  border-radius: 12px;
  text-align: center;
`;

const StreakValue = styled.div`
  font-size: 3rem;
  font-weight: bold;
  color: ${theme.colors.primary};
  margin-bottom: 0.5rem;
`;

const StreakLabel = styled.div`
  font-size: 1rem;
  color: ${theme.colors.text};
`;

const WeeklyChart = styled.div`
  margin-top: 1.5rem;
  display: flex;
  justify-content: space-around;
  align-items: flex-end;
  height: 100px;
`;

const DayBar = styled.div<{ height: number; isToday?: boolean }>`
  width: 30px;
  height: ${props => props.height}%;
  background: ${props => props.isToday ? theme.colors.primary : 'rgba(139, 69, 19, 0.3)'};
  border-radius: 4px 4px 0 0;
  position: relative;
  transition: all ${theme.transitions.default};
  
  &:hover {
    background: ${theme.colors.primary};
  }
`;

const DayLabel = styled.div`
  position: absolute;
  bottom: -20px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 0.75rem;
  color: ${theme.colors.textLight};
`;

interface ProgressData {
  pagesRead: number;
  timeSpent: string;
  volumesCompleted: number;
  passagesExplored: number;
  currentStreak: number;
  weeklyActivity: number[];
  milestones: {
    id: string;
    name: string;
    description: string;
    achieved: boolean;
    date?: string;
    icon: string;
  }[];
}

interface ProgressTrackerProps {
  data: ProgressData;
}

const ProgressTracker: React.FC<ProgressTrackerProps> = ({ data }) => {
  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const today = new Date().getDay();

  return (
    <TrackerContainer>
      <Title>Your Reading Journey</Title>
      
      <StatsGrid>
        <StatCard>
          <StatValue>{data.pagesRead.toLocaleString()}</StatValue>
          <StatLabel>Pages Read</StatLabel>
        </StatCard>
        
        <StatCard>
          <StatValue>{data.timeSpent}</StatValue>
          <StatLabel>Time Invested</StatLabel>
        </StatCard>
        
        <StatCard>
          <StatValue>{data.volumesCompleted}/7</StatValue>
          <StatLabel>Volumes Completed</StatLabel>
        </StatCard>
        
        <StatCard>
          <StatValue>{data.passagesExplored}</StatValue>
          <StatLabel>Passages Explored</StatLabel>
        </StatCard>
      </StatsGrid>
      
      <ReadingStreak>
        <StreakValue>🔥 {data.currentStreak}</StreakValue>
        <StreakLabel>Day Reading Streak</StreakLabel>
        
        <WeeklyChart>
          {data.weeklyActivity.map((activity, index) => (
            <DayBar 
              key={index} 
              height={activity} 
              isToday={index === today}
            >
              <DayLabel>{days[index]}</DayLabel>
            </DayBar>
          ))}
        </WeeklyChart>
      </ReadingStreak>
      
      <MilestoneSection>
        <MilestoneTitle>🏆 Milestones</MilestoneTitle>
        <MilestoneList>
          {data.milestones.map(milestone => (
            <Milestone key={milestone.id} achieved={milestone.achieved}>
              <MilestoneIcon achieved={milestone.achieved}>
                {milestone.icon}
              </MilestoneIcon>
              <MilestoneContent>
                <MilestoneName>{milestone.name}</MilestoneName>
                <MilestoneDescription>{milestone.description}</MilestoneDescription>
              </MilestoneContent>
              {milestone.achieved && milestone.date && (
                <AchievementDate>{milestone.date}</AchievementDate>
              )}
            </Milestone>
          ))}
        </MilestoneList>
      </MilestoneSection>
    </TrackerContainer>
  );
};

export default ProgressTracker;