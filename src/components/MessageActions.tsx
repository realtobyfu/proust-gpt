import React from 'react';
import styled from 'styled-components';
import { theme } from '../styles/theme';

const ActionsContainer = styled.div`
  display: flex;
  gap: 0.5rem;
  margin-top: 0.5rem;
  opacity: 0;
  transition: opacity ${theme.transitions.default};
  
  .message-wrapper:hover & {
    opacity: 1;
  }
`;

const ActionButton = styled.button`
  background: none;
  border: none;
  color: ${theme.colors.textLight};
  font-size: 0.875rem;
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  transition: all ${theme.transitions.default};
  
  &:hover {
    background: rgba(0, 0, 0, 0.05);
    color: ${theme.colors.primary};
  }
`;

interface MessageActionsProps {
  onCopy: () => void;
  onRegenerate?: () => void;
}

const MessageActions: React.FC<MessageActionsProps> = ({ onCopy, onRegenerate }) => {
  return (
    <ActionsContainer>
      <ActionButton onClick={onCopy}>Copy</ActionButton>
      {onRegenerate && <ActionButton onClick={onRegenerate}>Regenerate</ActionButton>}
    </ActionsContainer>
  );
};

export default MessageActions;