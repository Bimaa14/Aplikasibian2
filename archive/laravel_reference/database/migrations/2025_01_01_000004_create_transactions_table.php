<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('transactions', function (Blueprint $table) {
            $table->id();
            $table->string('invoice_number')->unique();
            $table->date('date');
            $table->foreignId('customer_id')->nullable()->constrained()->nullOnDelete();
            $table->foreignId('user_id')->nullable()->constrained()->nullOnDelete(); // kasir
            $table->enum('payment_method', ['cash', 'credit']);
            $table->decimal('total_amount', 14, 2);
            $table->decimal('total_cost', 14, 2)->default(0);    // total modal barang
            $table->decimal('total_profit', 14, 2)->default(0);  // laba total (barang & jasa)
            $table->decimal('service_fee', 14, 2)->default(0);   // total komisi montir
            $table->enum('status', ['completed', 'returned'])->default('completed');
            $table->date('due_date')->nullable(); // jatuh tempo untuk pembayaran credit
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('transactions');
    }
};
