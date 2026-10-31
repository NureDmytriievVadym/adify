<script lang="ts">
  import { goto } from '$app/navigation';
  import Icon from '#lib/components/Icon.svelte';
  import { session, signOut } from '#lib/accounts/session.svelte.ts';

  const status = (verified: boolean) => (verified ? 'Verified' : 'Not verified');

  async function leave() {
    await signOut();
    await goto('/sign-in');
  }
</script>

<svelte:head><title>Your account — Adify</title></svelte:head>

<div class="container page-content register-page">
  <div class="page-intro">
    <span class="eyebrow">YOUR ACCOUNT</span>
    {#if session.account}
      <h1>Hello,<br /><span>{session.account.display_name}.</span></h1>
      <p>Your account details. Only your phone number is ever shown to other users.</p>
    {:else}
      <h1>Your<br /><span>account.</span></h1>
    {/if}
  </div>

  {#if session.account}
    <section class="register-card" aria-labelledby="profile-title">
      <h2 id="profile-title" class="account-title">Profile</h2>
      <dl class="account-details">
        <div>
          <dt>Role</dt>
          <dd class="account-role">{session.account.role}</dd>
        </div>
        <div>
          <dt>Email address</dt>
          <dd>{session.account.email} · {status(session.account.email_verified)}</dd>
        </div>
        <div>
          <dt>Phone number</dt>
          <dd>{session.account.phone} · {status(session.account.phone_verified)}</dd>
        </div>
      </dl>
      {#if !session.account.email_verified || !session.account.phone_verified}
        <p class="field-hint">
          Verify your email address and phone number to reveal phone numbers, start chats, create
          listings, and place orders. Verification is coming in a later release.
        </p>
      {/if}
      {#if session.account.role === 'customer' || session.account.role === 'provider'}
        <a class="button button-dark register-submit" href="/listings/new"
          >{session.account.role === 'customer' ? 'Create an ad request' : 'Create an ad offering'}
          <Icon name="arrow" /></a
        >
      {/if}
      <a class="button button-outline register-submit" href="/listings/mine">My listings</a>
      <button class="button button-outline register-submit" type="button" onclick={leave}
        >Sign out</button
      >
    </section>
  {:else if session.restored}
    <section class="register-card">
      <p class="field-hint">Sign in to see your account.</p>
      <a class="button button-dark register-submit" href="/sign-in">Sign in <Icon name="arrow" /></a
      >
    </section>
  {:else}
    <p class="field-hint" role="status">Loading your account…</p>
  {/if}
</div>
