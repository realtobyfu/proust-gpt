import styled, { keyframes } from 'styled-components';

export const ChatContainer = styled.div`
  display: flex;
  width: 100vw;
  height: 100vh;
  height: 100dvh;
  background-color: #f7f4f0;
  overflow: hidden;
`;

export const Sidebar = styled.div<{ $isOpen: boolean }>`
  width: ${props => props.$isOpen ? '250px' : '0'};
  background-color: #faf8f5;
  border-right: ${props => props.$isOpen ? '1px solid #e0d8cf' : 'none'};
  padding: ${props => props.$isOpen ? '2rem' : '0'};
  box-sizing: border-box;
  color: #333;
  overflow-x: hidden;
  overflow-y: ${props => props.$isOpen ? 'auto' : 'hidden'};
  scrollbar-width: none;
  &::-webkit-scrollbar { display: none; }
  transition: all 0.3s ease;
`;

export const ChatContent = styled.div`
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;

  @media (min-width: 1025px) {
    flex-direction: row;
  }
`;

export const ConversationPane = styled.div<{ $readerOpen: boolean; $splitPercent: number }>`
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  transition: flex 0.3s ease;

  @media (min-width: 1025px) {
    flex: ${props => props.$readerOpen ? `0 0 ${props.$splitPercent}%` : '1'};
  }
`;

export const Divider = styled.div`
  width: 6px;
  cursor: col-resize;
  background: transparent;
  position: relative;
  flex-shrink: 0;

  &::after {
    content: '';
    position: absolute;
    top: 0;
    bottom: 0;
    left: 2px;
    width: 2px;
    background: #e0d8cf;
    transition: background 0.15s;
  }

  &:hover::after {
    background: #8b4513;
  }
`;

export const Header = styled.div`
  background-color: #faf8f5;
  border-bottom: 1px solid #e0d8cf;
  padding: 1.25rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

export const BackButton = styled.button`
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background: rgba(139, 69, 19, 0.05);
  border: none;
  border-radius: 20px;
  padding: 0.4rem 1rem;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.85rem;
  color: #8b4513;
  cursor: pointer;
  transition: all 0.15s ease;

  &:hover {
    background: rgba(139, 69, 19, 0.1);
  }
`;

export const ModeSwitcher = styled.div`
  display: inline-flex;
  border: 1px solid #e0d8cf;
  border-radius: 20px;
  overflow: hidden;
  background: #fff;
`;

export const ModeSwitchButton = styled.button<{ $active: boolean; $mode: 'explore' | 'reflect' }>`
  border: none;
  background: ${props => props.$active
    ? (props.$mode === 'reflect' ? 'rgba(90, 107, 90, 0.14)' : 'rgba(139, 69, 19, 0.1)')
    : 'transparent'};
  color: ${props => props.$active
    ? (props.$mode === 'reflect' ? '#5a6b5a' : '#8b4513')
    : '#8a8178'};
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.82rem;
  font-weight: ${props => props.$active ? 600 : 400};
  padding: 0.4rem 0.95rem;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;

  &:hover {
    color: ${props => props.$mode === 'reflect' ? '#5a6b5a' : '#8b4513'};
  }
`;

export const HeaderTextButton = styled.button`
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background: none;
  border: none;
  padding: 0;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.9rem;
  color: #8b4513;
  text-decoration: underline;
  cursor: pointer;

  &:hover {
    color: #6b3410;
  }
`;

export const CopyNotice = styled.div`
  position: fixed;
  bottom: 6.5rem;
  left: 50%;
  transform: translateX(-50%);
  background: #3a3028;
  color: #f7f4f0;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.82rem;
  padding: 0.5rem 1rem;
  border-radius: 20px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18);
  z-index: 200;
`;

export const SidebarTitleRow = styled.div`
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
`;

export const SidebarExportLink = styled.button`
  background: none;
  border: none;
  padding: 0;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.72rem;
  color: #8b4513;
  cursor: pointer;
  text-decoration: underline;

  &:hover {
    color: #6b3410;
  }
`;

export const MessagesArea = styled.div`
  flex: 1;
  padding: 2rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;

  &::-webkit-scrollbar {
    width: 5px;
  }
  &::-webkit-scrollbar-track {
    background: transparent;
  }
  &::-webkit-scrollbar-thumb {
    background: #d4ccc3;
    border-radius: 3px;
  }
`;

export const MessageBubble = styled.div<{ $isUser: boolean }>`
  background-color: ${props => props.$isUser ? '#6b3410' : '#f0ebe4'};
  border-radius: ${props => props.$isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px'};
  border: ${props => props.$isUser ? 'none' : '1px solid #e0d8cf'};
  border-left: ${props => !props.$isUser ? '3px solid #8b4513' : undefined};
  color: ${props => props.$isUser ? '#fff' : '#3a3a3a'};
  padding: 1rem;
  margin-bottom: 1rem;
  max-width: ${props => props.$isUser ? '60%' : '80%'};
  align-self: ${props => props.$isUser ? 'flex-end' : 'flex-start'};
  font-family: 'Georgia', serif;
  line-height: 1.6;
`;

const blink = keyframes`
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
`;

export const StreamingCursor = styled.span`
  display: inline-block;
  width: 2px;
  height: 1em;
  background-color: #8b4513;
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: ${blink} 1s infinite;
`;

export const SynthesisBanner = styled.div`
  border-left: 3px solid #c4a882;
  background: rgba(196, 168, 130, 0.08);
  padding: 0.75rem 1rem;
  margin-bottom: 0.75rem;
  font-family: 'Georgia', serif;
  font-style: italic;
  font-size: 0.9rem;
  color: #555;
  line-height: 1.5;
  border-radius: 0 6px 6px 0;
  max-width: 80%;
  align-self: flex-start;
`;

export const ResultsHeader = styled.div`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.82rem;
  color: #6e6459;
  margin-bottom: 0.5rem;
  max-width: 80%;
  align-self: flex-start;
`;

export const FloatingInputArea = styled.div`
  padding: 1rem 2rem 1.5rem;
  position: relative;
`;

export const InputLabel = styled.div`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.75rem;
  color: #6e6459;
  margin-bottom: 0.4rem;
  padding-left: 1rem;
`;

export const InputPill = styled.div`
  display: flex;
  align-items: center;
  position: relative;
  max-width: 800px;
  margin: 0 auto;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid #d4ccc3;
  border-radius: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  transition: box-shadow 0.2s ease, border-color 0.2s ease;

  &:focus-within {
    border-color: #8b4513;
    box-shadow: 0 4px 20px rgba(139, 69, 19, 0.1);
  }
`;

export const Input = styled.input`
  width: 100%;
  padding: 0.9rem 1.2rem;
  padding-right: 3rem;
  border: none;
  border-radius: 24px;
  font-size: 1rem;
  color: #333;
  background: transparent;
  font-family: 'Georgia', serif;

  &::placeholder {
    color: #7a6e5e;
  }

  &:focus {
    outline: none;
  }
`;

export const SendButton = styled.button`
  position: absolute;
  right: 8px;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: none;
  background-color: #8b4513;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: background-color 0.2s ease;

  &:hover {
    background-color: #6b3410;
  }

  &:disabled {
    background-color: #ccc;
    cursor: default;
  }
`;

export const StopButton = styled.button`
  background-color: #8b4513;
  color: white;
  border: none;
  border-radius: 20px;
  padding: 0.5rem 1rem;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.9rem;
  cursor: pointer;
  margin-right: 0.5rem;

  &:hover {
    background-color: #6b3410;
  }
`;

const pulse = keyframes`
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1); }
`;

export const LoadingIndicator = styled.div`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.9rem;
  color: #8b4513;
  text-align: center;
  margin: 1rem 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
`;

export const LoadingDot = styled.span<{ $delay: string }>`
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: #8b4513;
  animation: ${pulse} 1.4s ease-in-out infinite;
  animation-delay: ${props => props.$delay};
`;

export const HamburgerButton = styled.button`
  background: none;
  border: none;
  color: #8b4513;
  cursor: pointer;
  padding: 0.3rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: color 0.2s ease;

  &:hover {
    color: #6b3410;
  }
`;


export const SidebarSection = styled.div`
  margin-bottom: 2rem;
`;

export const SidebarTitle = styled.h3`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 1rem;
  margin-bottom: 0.5rem;
  color: #333;
`;

export const SidebarList = styled.ul`
  list-style: none;
  padding: 0;
  margin: 0;
`;

export const SidebarItem = styled.li`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.9rem;
  padding: 0.25rem 0;
  color: #666;
  cursor: pointer;
  transition: color 0.2s ease;

  &:hover {
    color: #8b4513;
  }
`;

export const ErrorMessage = styled.div`
  background-color: #fdf6f0;
  border: 1px solid #e0c8b0;
  color: #8b4513;
  border-radius: 10px;
  padding: 1rem;
  margin-bottom: 1rem;
  max-width: 80%;
  align-self: flex-start;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.9rem;

  &::before {
    content: '\26A0  ';
  }
`;

export const RetryButton = styled.button`
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  margin-top: 0.6rem;
  background: rgba(139, 69, 19, 0.08);
  border: 1px solid #c4a882;
  border-radius: 20px;
  padding: 0.35rem 0.9rem;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.82rem;
  color: #8b4513;
  cursor: pointer;
  transition: background 0.15s ease;

  &:hover {
    background: rgba(139, 69, 19, 0.15);
  }
`;

export const StoppedNote = styled.div`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.72rem;
  font-style: italic;
  color: #6e6459;
  margin: 0.25rem 0 1rem;
  max-width: 80%;
  align-self: flex-start;
`;

export const NewChatRow = styled.div`
  display: flex;
  gap: 6px;
  margin-bottom: 0.5rem;
`;

export const NewChatButton = styled.button<{ $mode?: 'explore' | 'reflect' }>`
  flex: 1;
  padding: 0.4rem 0;
  background: ${props => props.$mode === 'reflect' ? 'rgba(90, 107, 90, 0.06)' : 'rgba(139, 69, 19, 0.08)'};
  border: 1px dashed ${props => props.$mode === 'reflect' ? '#8a9b8a' : '#c4a882'};
  border-radius: 8px;
  color: ${props => props.$mode === 'reflect' ? '#5a6b5a' : '#8b4513'};
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.72rem;
  line-height: 1.2;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.3rem;
  transition: background 0.2s ease;

  &:hover {
    background: ${props => props.$mode === 'reflect' ? 'rgba(90, 107, 90, 0.15)' : 'rgba(139, 69, 19, 0.15)'};
  }
`;

export const SessionItem = styled.div<{ $active: boolean }>`
  padding: 0.5rem 0.6rem;
  border-radius: 6px;
  cursor: pointer;
  background: ${props => props.$active ? 'rgba(139, 69, 19, 0.1)' : 'transparent'};
  border-left: ${props => props.$active ? '3px solid #8b4513' : '3px solid transparent'};
  margin-bottom: 0.25rem;
  position: relative;
  transition: background 0.15s ease;

  &:hover {
    background: rgba(139, 69, 19, 0.06);
  }

  &:hover .delete-btn {
    opacity: 1;
  }
`;

export const SessionTitle = styled.div`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.82rem;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 1.2rem;
`;

export const SessionMeta = styled.div`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.7rem;
  color: #6e6459;
  margin-top: 0.15rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
`;

export const SessionModeTag = styled.span<{ $mode: string }>`
  font-size: 0.65rem;
  padding: 0.05rem 0.35rem;
  border-radius: 3px;
  background: ${props => props.$mode === 'reflect' ? 'rgba(90, 107, 90, 0.12)' : 'rgba(139, 69, 19, 0.08)'};
  color: ${props => props.$mode === 'reflect' ? '#5a6b5a' : '#8b4513'};
`;

export const DeleteButton = styled.button`
  position: absolute;
  top: 0.45rem;
  right: 0.3rem;
  background: none;
  border: none;
  color: #c4a882;
  cursor: pointer;
  font-size: 0.9rem;
  line-height: 1;
  padding: 0.1rem 0.25rem;
  border-radius: 3px;
  opacity: 0.5;
  transition: opacity 0.15s, color 0.15s;

  &:hover,
  &:focus-visible {
    opacity: 1;
    color: #a03030;
    background: rgba(160, 48, 48, 0.08);
  }

  @media (hover: hover) {
    opacity: 0;
  }
`;

export const EmptyState = styled.div`
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1.2rem;
`;

export const EmptyStateTitle = styled.h2`
  font-family: 'Belgrano', serif;
  font-weight: 400;
  font-size: 1.3rem;
  color: #2a2a2a;
  margin: 0;
`;

export const SuggestionChips = styled.div`
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
  justify-content: center;
`;

export const SuggestionChip = styled.button`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.85rem;
  color: #3a3028;
  background: rgba(58, 48, 40, 0.04);
  border: 1px solid #d4ccc3;
  border-radius: 20px;
  padding: 0.5rem 1rem;
  cursor: pointer;
  transition: all 0.15s ease;

  &:hover {
    background: rgba(58, 48, 40, 0.1);
    border-color: #564a40;
  }
`;
