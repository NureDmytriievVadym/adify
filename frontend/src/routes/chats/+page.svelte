<script lang="ts">
  import Icon from '#lib/components/Icon.svelte';
  import { session } from '#lib/accounts/session.svelte.ts';
  import { fetchChats, roleName, type Chat, type ChatResult } from '#lib/chats/api.ts';

  let result: ChatResult<Chat[]> | null = $state(null);

  $effect(() => {
    if (!session.account) return;
    result = null;
    fetchChats().then((next) => (result = next));
  });
</script>

<svelte:head><title>Chats — Adify</title></svelte:head>

<div class="container page-content">
  <div class="page-intro">
    <span class="eyebrow">YOUR CHATS</span>
    <h1>Your <span>chats.</span></h1>
    <p>Conversations you started from a listing, and the ones others started on yours.</p>
  </div>

  {#if !session.account && session.restored}
    <p class="field-hint">Sign in to see your chats.</p>
    <a class="button button-dark" href="/sign-in">Sign in <Icon name="arrow" /></a>
  {:else if !session.account || !result}
    <p class="field-hint" role="status">Loading your chats…</p>
  {:else if !result.ok}
    <p class="form-alert" role="alert">{result.message}</p>
  {:else if result.value.length === 0}
    <p class="field-hint">No chats yet. Open a listing and choose Start chat.</p>
    <a class="button button-dark" href="/listings">Browse the marketplace <Icon name="arrow" /></a>
  {:else}
    <ul class="chat-list">
      {#each result.value as chat (chat.id)}
        <li>
          <a class="chat-row" href={`/chats/${chat.id}`}>
            <span class="avatar">{chat.counterpart.display_name.slice(0, 2).toUpperCase()}</span>
            <span class="chat-row-text">
              <strong>{chat.counterpart.display_name}</strong>
              <span
                >{roleName(chat.counterpart.role)} · {chat.listing?.title ??
                  'Deleted listing'}</span
              >
            </span>
            <Icon name="chevron" size={18} />
          </a>
        </li>
      {/each}
    </ul>
  {/if}
</div>
