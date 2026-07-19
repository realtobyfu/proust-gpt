import React from 'react';
import { useTranslation } from 'react-i18next';
import { ChatSessionSummary } from '../../hooks/useChatSessions';
import { Bookmark } from '../../types';
import {
  Sidebar,
  SidebarSection,
  NewChatRow,
  NewChatButton,
  SidebarTitle,
  SidebarTitleRow,
  SidebarExportLink,
  SidebarList,
  SidebarItem,
  SessionItem,
  SessionTitle,
  SessionMeta,
  SessionModeTag,
  DeleteButton,
} from '../../ChatPage.styles';

// Sidebar character shortcuts (module constant — avoids re-allocation per render).
const CHARACTERS = [
  'Marcel (Narrator)',
  'Swann',
  'Odette',
  'Gilberte',
  'Albertine',
  'Baron de Charlus',
  'Mme de Guermantes',
];

interface ChatSidebarProps {
  sidebarOpen: boolean;
  sessions: ChatSessionSummary[];
  currentSessionId: string | null;
  bookmarks: Bookmark[];
  language: string;
  onNewConversation: (mode: string) => void;
  onSelectSession: (id: string) => void;
  onDeleteSession: (e: React.MouseEvent, id: string) => void;
  /** Prefill the composer (character shortcut / bookmark click). */
  onFillInput: (value: string) => void;
  onExportBookmarks: () => void;
}

const ChatSidebar: React.FC<ChatSidebarProps> = ({
  sidebarOpen,
  sessions,
  currentSessionId,
  bookmarks,
  language,
  onNewConversation,
  onSelectSession,
  onDeleteSession,
  onFillInput,
  onExportBookmarks,
}) => {
  const { t } = useTranslation();

  return (
    <Sidebar as="nav" aria-label={t('chat.conversations')} $isOpen={sidebarOpen}>
      <SidebarSection>
        <NewChatRow>
          <NewChatButton $mode="explore" onClick={() => onNewConversation('explore_lost_time')} title={t('chat.modeExplore')}>
            + {t('chat.modeExplore')}
          </NewChatButton>
          <NewChatButton $mode="reflect" onClick={() => onNewConversation('reflect')} title={t('chat.modeReflect')}>
            + {t('chat.modeReflect')}
          </NewChatButton>
        </NewChatRow>
        <SidebarTitle>{t('chat.conversations')}</SidebarTitle>
        {sessions.length === 0 ? (
          <SidebarItem style={{ color: '#aaa', cursor: 'default' }}>
            {t('chat.noConversations')}
          </SidebarItem>
        ) : (
          sessions.map(s => (
            <SessionItem
              key={s.id}
              $active={s.id === currentSessionId}
              role="button"
              tabIndex={0}
              aria-current={s.id === currentSessionId ? 'true' : undefined}
              onClick={() => onSelectSession(s.id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onSelectSession(s.id);
                }
              }}
            >
              <SessionTitle>{s.title}</SessionTitle>
              <SessionMeta>
                <SessionModeTag $mode={s.mode}>
                  {s.mode === 'reflect' ? t('chat.modeReflect') : t('chat.modeExplore')}
                </SessionModeTag>
                {new Date(s.updatedAt).toLocaleDateString(language)}
              </SessionMeta>
              <DeleteButton
                className="delete-btn"
                onClick={(e) => onDeleteSession(e, s.id)}
                aria-label={t('chat.deleteConversation')}
                title={t('chat.deleteConversation')}
              >
                &times;
              </DeleteButton>
            </SessionItem>
          ))
        )}
      </SidebarSection>

      <SidebarSection>
        <SidebarTitle>{t('chat.characters')}</SidebarTitle>
        <SidebarList>
          {CHARACTERS.map(char => (
            <SidebarItem
              key={char}
              role="button"
              tabIndex={0}
              onClick={() => onFillInput(t('chat.tellMeAbout', { character: char }))}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onFillInput(t('chat.tellMeAbout', { character: char }));
                }
              }}
            >
              {char}
            </SidebarItem>
          ))}
        </SidebarList>
      </SidebarSection>

      <SidebarSection>
        <SidebarTitleRow>
          <SidebarTitle>{t('chat.bookmarks', { count: bookmarks.length })}</SidebarTitle>
          {bookmarks.length > 0 && (
            <SidebarExportLink onClick={onExportBookmarks} title={t('chat.exportBookmarks')}>
              {t('chat.exportBookmarks')}
            </SidebarExportLink>
          )}
        </SidebarTitleRow>
        <SidebarList>
          {bookmarks.length === 0 ? (
            <SidebarItem style={{ color: '#aaa', cursor: 'default' }}>
              {t('chat.noBookmarks')}
            </SidebarItem>
          ) : (
            bookmarks.map(bm => (
              <SidebarItem
                key={bm.id}
                role="button"
                tabIndex={0}
                onClick={() => onFillInput(`Tell me more about this passage: "${bm.text.slice(0, 80)}..."`)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onFillInput(`Tell me more about this passage: "${bm.text.slice(0, 80)}..."`);
                  }
                }}
                title={bm.text.slice(0, 200)}
              >
                {bm.book} &mdash; {bm.text.slice(0, 40)}...
              </SidebarItem>
            ))
          )}
        </SidebarList>
      </SidebarSection>
    </Sidebar>
  );
};

export default ChatSidebar;
