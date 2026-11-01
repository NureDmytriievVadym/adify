<script lang="ts">
  import { onDestroy, tick } from 'svelte';
  import {
    confirmCode,
    sendCode,
    type Channel,
    type ChannelStatus,
  } from '#lib/accounts/verification.ts';

  let {
    channel,
    destination,
    verified,
    status = null,
    initialCode = '',
  }: {
    channel: Channel;
    destination: string;
    verified: boolean;
    status?: ChannelStatus | null;
    initialCode?: string;
  } = $props();

  const isEmail = $derived(channel === 'email');
  // svelte-ignore state_referenced_locally
  let code = $state(initialCode);
  let sentHere = $state(false);
  let resendIn = $state(0);
  let feedback: { ok: boolean; message: string } | null = $state(null);
  let busy = $state(false);
  let input: HTMLInputElement | undefined = $state();
  let timer: ReturnType<typeof setInterval> | undefined;

  // The code field appears only when a usable code is out, or the email link brought one.
  const codeSent = $derived(sentHere || initialCode !== '' || !!status?.code_sent);

  function countdown(seconds: number) {
    clearInterval(timer);
    resendIn = seconds;
    timer = setInterval(() => {
      resendIn = Math.max(0, resendIn - 1);
      if (resendIn === 0) clearInterval(timer);
    }, 1000);
  }

  $effect(() => {
    if (status?.resend_in) countdown(status.resend_in);
  });
  onDestroy(() => clearInterval(timer));

  async function send() {
    busy = true;
    const result = await sendCode(channel);
    busy = false;
    feedback = result.ok ? null : result;
    if (!result.ok) return;
    sentHere = true;
    code = '';
    countdown(result.resendIn ?? 60);
    feedback = { ok: true, message: result.message };
    await tick();
    input?.focus();
  }

  async function confirm(event: SubmitEvent) {
    event.preventDefault();
    busy = true;
    feedback = await confirmCode(channel, code);
    busy = false;
  }
</script>

<div class="verification-step">
  <div class="verification-heading">
    <div>
      <h3>{isEmail ? 'Email address' : 'Phone number'}</h3>
      <p class="verification-destination">{destination}</p>
    </div>
    <span class="verification-badge" class:verified>{verified ? 'Verified' : 'Not verified'}</span>
  </div>

  {#if !verified && !codeSent}
    <p class="field-hint">
      {isEmail
        ? 'We will email a six-digit code to this address.'
        : 'We will text a six-digit code to this number.'}
    </p>
    <button class="button button-dark button-small" type="button" disabled={busy} onclick={send}
      >{busy ? 'Sending…' : isEmail ? 'Email me a code' : 'Text me a code'}</button
    >
  {:else if !verified}
    <form class="verification-form" novalidate onsubmit={confirm}>
      <label for={`${channel}-code`}
        >Enter the six-digit code we {isEmail ? 'emailed' : 'texted'} to you</label
      >
      <div class="verification-row">
        <input
          id={`${channel}-code`}
          name={`${channel}-code`}
          inputmode="numeric"
          autocomplete="one-time-code"
          maxlength="6"
          placeholder="000000"
          bind:value={code}
          bind:this={input}
        />
        <button
          class="button button-dark"
          type="submit"
          disabled={busy}
          aria-label={isEmail ? 'Verify email address' : 'Verify phone number'}>Verify</button
        >
      </div>
    </form>
    <p class="verification-resend">
      Didn’t get it?
      <button class="link-button" type="button" disabled={busy || resendIn > 0} onclick={send}
        >{resendIn > 0 ? `Send a new code in ${resendIn}s` : 'Send a new code'}</button
      >
    </p>
  {/if}

  {#if feedback}
    <p class={feedback.ok ? 'field-hint' : 'field-error'} role={feedback.ok ? 'status' : 'alert'}>
      {feedback.message}
    </p>
  {/if}
</div>
