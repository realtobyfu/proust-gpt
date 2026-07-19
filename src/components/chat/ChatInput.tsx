import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  FloatingInputArea,
  InputLabel,
  InputPill,
  Input,
  StopButton,
  SendButton,
} from '../../ChatPage.styles';

interface ChatInputProps {
  activeMode: string;
  userInput: string;
  onUserInput: (value: string) => void;
  isLoading: boolean;
  isStreaming: boolean;
  onSubmit: (e: React.FormEvent) => void;
  onStop: () => void;
}

const ChatInput: React.FC<ChatInputProps> = ({
  activeMode,
  userInput,
  onUserInput,
  isLoading,
  isStreaming,
  onSubmit,
  onStop,
}) => {
  const { t } = useTranslation();
  const isReflect = activeMode === 'reflect';

  return (
    <FloatingInputArea>
      <InputLabel>
        {isReflect ? t('chat.inputLabelReflect') : t('chat.inputLabelExplore')}
      </InputLabel>
      <InputPill as="form" onSubmit={onSubmit}>
        <Input
          type="text"
          placeholder={isReflect ? t('chat.placeholderReflect') : t('chat.placeholderExplore')}
          value={userInput}
          onChange={(e) => onUserInput(e.target.value)}
          disabled={isLoading}
          aria-label={isReflect ? t('chat.inputLabelReflect') : t('chat.inputLabelExplore')}
        />
        {isStreaming ? (
          <StopButton type="button" onClick={onStop}>
            {t('common.stop')}
          </StopButton>
        ) : (
          <SendButton type="submit" disabled={isLoading} aria-label={t('common.search')}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
          </SendButton>
        )}
      </InputPill>
    </FloatingInputArea>
  );
};

export default ChatInput;
