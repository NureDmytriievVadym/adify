<script lang="ts">
  import { page } from '$app/state';
  import Icon from '#lib/components/Icon.svelte';
  import { session } from '#lib/accounts/session.svelte.ts';
  import { goto } from '$app/navigation';
  import { fetchChat, roleName, type Chat, type ChatResult } from '#lib/chats/api.ts';
  import CreateOrderForm from '#lib/components/CreateOrderForm.svelte';
  import { formatUah } from '#lib/listings/catalog.ts';
  import { fetchChatOrders, statusLabel, type Order } from '#lib/orders/api.ts';

  let result: ChatResult<Chat> | null = $state(null);
  let orders: Order[] = $state([]);
  let creating = $state(false);

  $effect(() => {
    const id = page.params.id;
    if (!session.account || !id) return;
    result = null;
    orders = [];
    creating = false;
    fetchChat(id).then((next) => {
      if (page.params.id === id) result = next;
    });
    fetchChatOrders(id).then((next) => {
      if (page.params.id === id && next.ok) orders = next.value;
    });
  });

  // FR-031: only the listing owner records orders, and only while the listing takes them.
  const isOwner = $derived.by(() => {
    const current = result as ChatResult<Chat> | null;
    return !!(current?.ok && current.value.listing?.owner_id === session.account?.id);
  });

  const stateLabel = (status: string) =>
    ({ paused: 'Paused', expired: 'Expired', soft_deleted: 'Deleted' })[status] ?? null;
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
                <span class="listing-state" class:expired={chat.listing.status !== 'paused'}
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

    <section class="register-card chat-card chat-orders" aria-labelledby="orders-title">
      <div class="chat-orders-heading">
        <h2 id="orders-title" class="account-title">Orders</h2>
        {#if isOwner && chat.listing?.status === 'active' && !creating}
          <button
            class="button button-dark button-small"
            type="button"
            onclick={() => (creating = true)}>Create order</button
          >
        {/if}
      </div>
      {#if isOwner && chat.listing && chat.listing.status !== 'active'}
        <p class="field-hint">
          This listing is {chat.listing.status} and is not accepting new orders.
        </p>
      {/if}
      {#if creating}
        <CreateOrderForm
          chatId={chat.id}
          oncreated={(order) => goto(`/orders/${order.id}`)}
          oncancel={() => (creating = false)}
        />
      {/if}
      {#if orders.length === 0}
        <p class="field-hint">
          {isOwner
            ? 'No orders yet. When you agree on the details, create an order here.'
            : 'No orders yet. The listing owner creates the order once you agree on the details.'}
        </p>
      {:else}
        <ul class="order-list">
          {#each orders as order (order.id)}
            <li>
              <a class="chat-row" href={`/orders/${order.id}`}>
                <span class="chat-row-text">
                  <strong>{formatUah(Number(order.price_uah))}</strong>
                  <span>{order.details}</span>
                </span>
                <span class="order-state">{statusLabel[order.status]}</span>
              </a>
            </li>
          {/each}
        </ul>
      {/if}
    </section>
  {/if}
</div>
