<script lang="ts">
  import { page } from '$app/state';
  import Icon from '#lib/components/Icon.svelte';
  import { session } from '#lib/accounts/session.svelte.ts';
  import { categoryName, formatUah } from '#lib/listings/catalog.ts';
  import {
    fetchOrder,
    fetchPayment,
    formatDay,
    startPayment,
    statusLabel,
    type Order,
    type OrderResult,
    type Payment,
  } from '#lib/orders/api.ts';

  let result: OrderResult<Order> | null = $state(null);
  let paymentNote: string | null = $state(null);
  let paymentError: string | null = $state(null);
  let paying = $state(false);

  // What the customer sees after Mono sends them back to the order.
  function returnNote(payment: Payment): string | null {
    if (payment.status === 'created' || payment.status === 'processing')
      return 'Mono is still processing the payment. Refresh this page in a moment.';
    if (payment.status === 'failure')
      return `The payment did not go through${payment.failure_reason ? ` (${payment.failure_reason})` : ''}. You can try again.`;
    if (payment.status === 'expired') return 'The payment page expired. Start the payment again.';
    return null;
  }

  async function load(id: string, returning: boolean) {
    // The payment is read first: reading it syncs the invoice, which may mark the order paid.
    const payment = returning ? await fetchPayment(id) : null;
    const next = await fetchOrder(id);
    if (page.params.id !== id) return;
    result = next;
    paymentNote = payment?.ok ? returnNote(payment.value) : null;
  }

  // FR-038: the customer pays on Mono's page; the funds are held until work starts.
  async function pay(order: Order) {
    paying = true;
    paymentError = null;
    const started = await startPayment(order.id);
    if (started.ok && started.value.page_url) return window.location.assign(started.value.page_url);
    paying = false;
    paymentError = started.ok ? 'The payment could not be started. Try again.' : started.message;
  }

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
    paymentNote = null;
    paymentError = null;
    load(id, page.url.searchParams.get('payment') === 'return');
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

      {#if order.status === 'awaiting_payment' || order.status === 'paid'}
        <h2 class="account-title">Payment</h2>
        {#if order.status === 'paid'}
          <p class="field-hint" role="status">
            Paid{order.paid_at ? ` on ${formatDay(order.paid_at.slice(0, 10))}` : ''}. Mono holds
            the funds until the provider starts work.
          </p>
        {:else if order.customer.id === session.account?.id}
          <p class="field-hint">
            Pay by card in UAH through Mono. The funds are held, not charged, until the provider
            starts work.
          </p>
          {#if paymentNote}<p class="form-alert" role="alert">{paymentNote}</p>{/if}
          {#if paymentError}<p class="form-alert" role="alert">{paymentError}</p>{/if}
          <button
            type="button"
            class="button button-dark"
            disabled={paying}
            onclick={() => pay(order)}
            >{paying ? 'Opening Mono…' : `Pay ${formatUah(Number(order.price_uah))}`}
            <Icon name="arrow" /></button
          >
        {:else}
          <p class="field-hint">Waiting for the customer to pay through Mono.</p>
        {/if}
      {/if}

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
