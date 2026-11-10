<script lang="ts">
  import { page } from '$app/state';
  import Icon from '#lib/components/Icon.svelte';
  import { session } from '#lib/accounts/session.svelte.ts';
  import { categoryName, formatUah } from '#lib/listings/catalog.ts';
  import {
    fetchOrder,
    formatDay,
    statusLabel,
    type Order,
    type OrderResult,
  } from '#lib/orders/api.ts';

  let result: OrderResult<Order> | null = $state(null);

  // FR-036: the listing owner may be either party, so the page marks who is who.
  function partyNote(order: Order, partyId: string) {
    const me = session.account?.id;
    const other = order.customer.id === me ? order.provider.id : order.customer.id;
    const owner = order.is_listing_owner ? me : other;
    const notes = [partyId === me && 'you', partyId === owner && 'listing owner'].filter(Boolean);
    return notes.length ? ` (${notes.join(', ')})` : '';
  }

  $effect(() => {
    const id = page.params.id;
    if (!session.account || !id) return;
    result = null;
    fetchOrder(id).then((next) => {
      if (page.params.id === id) result = next;
    });
  });
</script>

<svelte:head><title>Order — Adify</title></svelte:head>

<div class="container page-content">
  {#if !session.account && session.restored}
    <h1 class="visually-hidden">Order</h1>
    <p class="field-hint">Sign in to see this order.</p>
    <a class="button button-dark" href="/sign-in">Sign in <Icon name="arrow" /></a>
  {:else if !session.account || !result}
    <h1 class="visually-hidden">Order</h1>
    <p class="field-hint" role="status">Loading the order…</p>
  {:else if !result.ok}
    <h1 class="visually-hidden">Order</h1>
    <p class="form-alert" role="alert">{result.message}</p>
  {:else}
    {@const order = result.value}
    {#if order.chat_id}
      <a class="text-link chat-back" href={`/chats/${order.chat_id}`}
        ><Icon name="chevron" size={16} /> Back to the chat</a
      >
    {/if}
    <section class="register-card chat-card" aria-labelledby="order-title">
      <div class="order-heading">
        <div>
          <span class="eyebrow">ORDER</span>
          <h1 id="order-title">{formatUah(Number(order.price_uah))}</h1>
        </div>
        <span class="order-state">{statusLabel[order.status]}</span>
      </div>
      <dl class="account-details">
        <div>
          <dt>Listing</dt>
          <dd>
            <a class="text-link" href={`/listings/${order.listing.id}`}>{order.listing.title}</a>
          </dd>
        </div>
        <div>
          <dt>Customer</dt>
          <dd>
            {order.customer.display_name}{partyNote(order, order.customer.id)}
          </dd>
        </div>
        <div>
          <dt>Provider</dt>
          <dd>
            {order.provider.display_name}{partyNote(order, order.provider.id)}
          </dd>
        </div>
        <div>
          <dt>Details</dt>
          <dd class="order-details">{order.details}</dd>
        </div>
        <div>
          <dt>Deadline</dt>
          <dd>{order.deadline ? formatDay(order.deadline) : 'No overall deadline'}</dd>
        </div>
      </dl>

      <h2 class="account-title">Work stages</h2>
      {#if order.stages.length === 0}
        <p class="field-hint">No separate stages.</p>
      {:else}
        <ol class="order-stage-list">
          {#each order.stages as stage, index (index)}
            <li>
              <strong>{stage.title}</strong>
              <span>{stage.deadline ? `Due ${formatDay(stage.deadline)}` : 'No deadline'}</span>
            </li>
          {/each}
        </ol>
      {/if}

      <h2 class="account-title">Technical requirements</h2>
      <p class="field-hint">
        Copied from the {order.requirements.listing_type === 'offer' ? 'offering' : 'request'} in
        {categoryName(order.requirements.category)} when the order was created. Later changes to the listing
        do not affect this order.
      </p>
      {#if order.requirements.has_requirements}
        <dl class="account-details">
          {#each order.requirements.specs as spec (spec.label)}
            <div>
              <dt>{spec.label}</dt>
              <dd>{spec.value}</dd>
            </div>
          {/each}
        </dl>
      {:else}
        <p class="order-no-requirements">
          No technical requirements: the customer did not set any for this ad request.
        </p>
      {/if}
    </section>
  {/if}
</div>
