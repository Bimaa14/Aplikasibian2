<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('products', function (Blueprint $table) {
            $table->id();
            $table->enum('type', ['barang', 'jasa']);
            $table->string('sku')->unique();
            $table->string('name');
            $table->string('brand')->nullable();
            $table->string('size')->nullable();
            $table->unsignedInteger('stock')->default(0);
            $table->decimal('cost_price', 12, 2)->default(0);    // modal
            $table->decimal('selling_price', 12, 2)->default(0); // harga jual
            $table->decimal('service_fee', 12, 2)->default(0);   // komisi montir (khusus jasa)
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('products');
    }
};
