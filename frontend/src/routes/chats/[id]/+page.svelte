<script lang="ts">
  import { page } from '$app/state';
  import Icon from '#lib/components/Icon.svelte';
  import { session } from '#lib/accounts/session.svelte.ts';
  import { fetchChat, roleName, type Chat, type ChatResult } from '#lib/chats/api.ts';

  let result: ChatResult<Chat> | null = $state(null);

  $effect(() => {
    const id = page.params.id;
    if (!session.account || !id) return;
    result = null;
    fetchChat(id).then((next) => {
      if (page.params.id === id) result = next;
    });
  });

  const stateLabel = (status: string) =>
    status === 'paused' ? 'Paused' : status === 'expired' ? 'Expired' : null;
</script>

<svelte:head>
  <title>{result?.ok ? `Chat with ${result.value.counterpart.display_name}` : 'Chat'} — Adify</title
  >
</svelte:head>

<div class="container page-content">
  <a class="text-link chat-back" href="/chats"><Icon name="chevron" size={16} /> All chats</a>

  {#if !session.account && session.restored}
    <h1 class="visually-hidden">Chat</h1>
    <p class="field-hint">Sign in to open this chat.</p>
    <a class="button button-dark" href="/sign-in">Sign in <Icon name="arrow" /></a>
  {:else if !session.account || !result}
    <h1 class="visually-hidden">Chat</h1>
    <p class="field-hint" role="status">Loading the chat…</p>
  {:else if !result.ok}
    <h1 class="visually-hidden">Chat</h1>
    <p class="form-alert" role="alert">{result.message}</p>
  {:else}
    {@const chat = result.value}
    <section class="register-card chat-card" aria-labelledby="chat-title">
      <div class="chat-header">
        <span class="avatar avatar-large"
          >{chat.counterpart.display_name.slice(0, 2).toUpperCase()}</span
        >
        <div>
          <h1 id="chat-title">Chat with {chat.counterpart.display_name}</h1>
          <p class="field-hint">
            {roleName(chat.counterpart.role)} ·
            {#if chat.listing}
              <a class="text-link" href={`/listings/${chat.listing.id}`}>{chat.listing.title}</a>
              {#if stateLabel(chat.listing.status)}
                <span class="listing-state" class:expired={chat.listing.status === 'expired'}
                  >{stateLabel(chat.listing.status)}</span
                >
              {/if}
            {:else}
              The listing was deleted
            {/if}
          </p>
        </div>
      </div>
      <div class="chat-messages" aria-live="polite">
        <p class="field-hint">No messages yet.</p>
      </div>
      <p class="small-note">
        Sending messages and files is coming soon. Keep written contact inside Adify: email
        addresses are never shown to other users.
      </p>
    </section>
  {/if}
</div>
