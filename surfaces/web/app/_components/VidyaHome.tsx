'use client';

import { Composer, SuggestionChip } from '@classess/design-system';
import { Rail } from './Rail';
import { VoiceCapsule } from './VoiceCapsule';
import { MessageThread } from './MessageThread';
import { useOnline } from '@/lib/useOnline';
import { useRole } from '@/lib/RoleContext';
import { GREETING, HOME_CHIPS, ROLE_LABELS } from '@/lib/mock';
import { useVidya } from '@/lib/useVidya';
import { useStore } from '@/lib/useStore';
import { profileSummaryLine } from '@/lib/store';

/**
 * The conversation-first home. By default near-empty and calm: a short greeting,
 * one centred composer, and a few quiet suggestion chips beneath it. When the
 * user sends a message the thread renders; a self-contained result renders
 * inline as a generative component, and a big task routes to its page. Role is
 * swappable via the rail; the home is role-shaped over one shell.
 */
export function VidyaHome() {
  const online = useOnline();
  const { role, setRole } = useRole();
  const { profile } = useStore();
  // The ONE Vidya send path, shared with the docked panel via useVidya.
  const { messages, thinking, send, applyVoiceTurn, reset } = useVidya();

  const hasThread = messages.length > 0 || thinking;

  function newConversation() {
    reset();
  }

  // Vidya's spoken reply (from the voice capsule) lands in the thread through
  // the SAME action path as text — render an inline spec, follow a navigate.
  function receiveVoiceReply(text: string, actions: Parameters<typeof applyVoiceTurn>[1]) {
    applyVoiceTurn(text, actions);
  }

  return (
    // data-surface binds --accent to the active role's hue (the shared accent
    // contract): student -> tiffany, teacher -> cobalt, admin -> violet,
    // parent -> amber. --signature stays reserved for the brand mark + ignite.
    <div className="app-frame" data-surface={role}>
      <Rail role={role} onRoleChange={setRole} onNewConversation={newConversation} />

      <main className="app-main">
        {!online ? (
          <div className="offline-banner" role="status">
            You are offline. The core flows still work; new conversations will sync when you
            reconnect.
          </div>
        ) : null}

        <div className={`home-canvas${hasThread ? ' has-thread' : ''}`}>
          {hasThread ? (
            <div className="home-center" style={{ maxWidth: 720 }}>
              <MessageThread messages={messages} thinking={thinking} />
              <Composer onSend={send} placeholder="Reply, or ask for the next thing" />
            </div>
          ) : (
            <div className="home-center">
              <div className="home-greeting">
                <p className="overline" style={{ justifyContent: 'center' }}>
                  {ROLE_LABELS[role]} home
                </p>
                <h1 className="display-sm" style={{ margin: '0 auto', maxWidth: 560 }}>
                  {GREETING[role]}
                </h1>
                {profile ? (
                  <p className="body-sm muted" style={{ margin: 'var(--space-3) auto 0', maxWidth: 520 }}>
                    {profileSummaryLine(profile)}
                  </p>
                ) : null}
              </div>

              <div className="home-composer-row">
                <Composer onSend={send} placeholder="Ask anything, or describe where you want to start" />
                <VoiceCapsule onReply={receiveVoiceReply} role={role} />
              </div>

              <div className="home-chips">
                {HOME_CHIPS[role].map((chip) => (
                  <SuggestionChip key={chip} spark onClick={() => send(chip)}>
                    {chip}
                  </SuggestionChip>
                ))}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
