<script>
	// Layout override: UCT branding — the header wordmark (static/uct-*.svg,
	// UCT brand colours Pantone 2925 C #009ADA / 539 C #00243A) and the
	// uct.ac.za typography treatment (Montserrat headings, Roboto body).
	// The "Built with Evidence" footer link is deliberately kept.
	import '@evidence-dev/tailwind/fonts.css';
	import '../app.css';
	import { EvidenceDefaultLayout } from '@evidence-dev/core-components';
	import { onMount } from 'svelte';
	export let data;

	let userName = '';
	onMount(() => {
		const m = document.cookie.match(/(?:^|;\s*)uct_user=([^;]+)/);
		if (m) userName = decodeURIComponent(m[1]);
	});
</script>

<svelte:head>
	<link rel="preconnect" href="https://fonts.googleapis.com" />
	<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
	<link
		href="https://fonts.googleapis.com/css2?family=Montserrat:wght@300;600;700&family=Roboto:wght@400;500;700&display=swap"
		rel="stylesheet"
	/>
	<link rel="icon" href="/favicon.ico" sizes="16x16" />
</svelte:head>

<EvidenceDefaultLayout {data} lightLogo="/uct-official-light.svg" darkLogo="/uct-official-dark.svg">
	<slot slot="content" />
</EvidenceDefaultLayout>

<span class="uct-user-slot">
	{#if userName}<span class="uct-user">{userName}</span><span class="uct-sep">·</span>{/if}
	<a href="/auth/logout" class="uct-signout" rel="external">Sign out</a>
</span>

<style>
	:global(body) {
		font-family: Roboto, system-ui, -apple-system, 'Segoe UI', sans-serif;
	}
	:global(h1.title),
	:global(h1.markdown),
	:global(h2.markdown),
	:global(h3.markdown),
	:global(h4.markdown),
	:global(.markdown h1),
	:global(.markdown h2),
	:global(.markdown h3) {
		font-family: Montserrat, Roboto, system-ui, sans-serif !important;
		letter-spacing: 0.01em;
	}
	:global(h1.title),
	:global(h1.markdown) {
		font-weight: 300;
	}
	/* uct.ac.za signature: header band edged in UCT blue */
	:global(header) {
		border-bottom: 3px solid #0098db !important;
	}
	.uct-user-slot {
		position: fixed;
		top: 0.8rem;
		right: 4.6rem;
		z-index: 60;
		display: flex;
		align-items: center;
		gap: 0.45rem;
		font-family: Montserrat, sans-serif;
		font-size: 0.68rem;
		letter-spacing: 0.06em;
	}
	.uct-user {
		font-weight: 500;
		opacity: 0.65;
		max-width: 14rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.uct-sep {
		opacity: 0.35;
	}
	.uct-signout {
		font-weight: 600;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: #0074a8;
		text-decoration: none;
	}
	.uct-signout:hover {
		color: #00243a;
	}
	@media print {
		.uct-user-slot {
			display: none;
		}
	}
</style>
