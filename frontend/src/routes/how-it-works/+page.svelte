<script lang="ts">
  import Icon from '#lib/components/Icon.svelte';

  function pointerTilt(node: HTMLElement) {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    function move(event: PointerEvent) {
      if (event.pointerType !== 'mouse') return;
      const bounds = node.getBoundingClientRect();
      const x = ((event.clientX - bounds.left) / bounds.width - 0.5) * 2;
      const y = ((event.clientY - bounds.top) / bounds.height - 0.5) * 2;
      node.style.setProperty('--tilt-x', `${x * 7}deg`);
      node.style.setProperty('--tilt-y', `${y * -7}deg`);
    }

    function reset() {
      node.style.setProperty('--tilt-x', '0deg');
      node.style.setProperty('--tilt-y', '0deg');
    }

    node.addEventListener('pointermove', move);
    node.addEventListener('pointerleave', reset);

    return {
      destroy() {
        node.removeEventListener('pointermove', move);
        node.removeEventListener('pointerleave', reset);
      },
    };
  }
</script>

<svelte:head
  ><title>How it works — Adify</title><meta
    name="description"
    content="Learn how Adify is being built to connect advertising customers and providers, from discovering a placement to reviewing the work."
  /></svelte:head
>

<div class="container page-content">
  <div class="how-intro-layout">
    <div class="page-intro">
      <span class="eyebrow">MEET ADIFY</span>
      <h1>Your idea.<br />Their space.<br /><span>A shared possibility.</span></h1>
      <p>
        Adify is an internet advertising marketplace for Ukraine.<br class="desktop-break" /> Here
        is the experience we are building for customers and providers.
      </p>
    </div>
    <div class="how-visual" aria-hidden="true">
      <span class="how-visual-orbit"></span>
      <span class="how-visual-label">IDEAS IN MOTION <i>✳</i></span>
      <div class="how-compass-tilt" use:pointerTilt>
        <svg class="how-compass-art" viewBox="0 0 400 400" fill="none">
          <circle cx="200" cy="200" r="151" stroke="#ff584177" />
          <circle cx="200" cy="200" r="132" stroke="#ff584144" stroke-dasharray="2 7" />
          <g class="how-compass-ticks" stroke="#ff584199" stroke-width="2">
            <path d="M200 37v20m0 286v20M37 200h20m286 0h20" />
            <path d="m84.7 84.7 14.2 14.2m202.2 202.2 14.2 14.2m0-230.6-14.2 14.2M98.9 301.1l-14.2 14.2" />
          </g>
          <path d="m200 75 28 97 97 28-97 28-28 97-28-97-97-28 97-28z" fill="#202020" />
          <path d="m200 75 28 97-28 28-28-28z" fill="#ff5841" />
          <path d="m200 200 28-28 97 28-97 28z" fill="#ff806c" />
          <path d="m200 200 28 28-28 97-28-97z" fill="#f3f2ee" />
          <path d="m200 200-28 28-97-28 97-28z" fill="#e94734" />
          <circle cx="200" cy="200" r="9" fill="#202020" stroke="#f3f2ee" stroke-width="3" />
          <text x="200" y="29" text-anchor="middle" class="how-compass-direction">N</text>
          <text x="373" y="204" text-anchor="middle" class="how-compass-direction">E</text>
          <text x="200" y="389" text-anchor="middle" class="how-compass-direction">S</text>
          <text x="27" y="204" text-anchor="middle" class="how-compass-direction">W</text>
        </svg>
      </div>
      <span class="how-visual-caption">GOOD IDEAS MOVE FORWARD <b>↗</b></span>
    </div>
  </div>
  <div class="audience-grid">
    <section class="audience-card">
      <span class="eyebrow">FOR CUSTOMERS</span>
      <h2>Find a place<br />for your brand.</h2>
      <p>
        Explore advertising offers or publish an ad request describing what you need. Discuss the
        details with a provider and agree on the scope.
      </p>
      <ul class="check-list">
        <li><Icon name="check" size={18} /> Discover six internet advertising categories</li>
        <li><Icon name="check" size={18} /> Agree on clear placement requirements</li>
        <li><Icon name="check" size={18} /> Review the work before completion</li>
      </ul>
    </section>
    <section class="audience-card provider-audience">
      <span class="eyebrow">FOR PROVIDERS</span>
      <h2>Make space<br />for good brands.</h2>
      <p>
        Offer an advertising placement or service with its technical requirements. Connect with
        customers and manage the agreed work in one place.
      </p>
      <ul class="check-list">
        <li><Icon name="check" size={18} /> Present your placement and price in UAH</li>
        <li><Icon name="check" size={18} /> Discuss the idea in Adify chat</li>
        <li><Icon name="check" size={18} /> Share evidence and submit work for review</li>
      </ul>
    </section>
  </div>
  <section class="how-details">
    <h2>A few things worth knowing.</h2>
    <div>
      <h3>One account. One marketplace role.</h3>
      <p>
        Each marketplace account is either a customer or a provider. Email and a Ukrainian phone
        number (+380) must be verified before protected actions.
      </p>
    </div>
    <div>
      <h3>Internet advertising, in six categories.</h3>
      <p>
        Website banners, sponsored articles, social media posts, video integrations, stream ads, and
        in-app mobile ads.
      </p>
    </div>
    <div>
      <h3>Payments in UAH, through Mono.</h3>
      <p>
        The planned payment flow holds funds on the customer’s card, charges them when the provider
        starts work, and keeps the funds with Adify until completion or an applicable refund. The
        default platform fee is 10% of the provider’s payout share.
      </p>
    </div>
    <a href="/listings" class="button button-dark"
      >Explore the marketplace preview <Icon name="arrow" size={18} /></a
    >
  </section>
</div>
